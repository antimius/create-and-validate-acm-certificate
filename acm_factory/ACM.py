import boto3
import tldextract
import aws_helpers
import time


class DNSValidatedACMCertClient():

    def __init__(self, domain, profile='default', r53_profile='default', region='us-east-1'):
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.r53_session = boto3.Session(profile_name=r53_profile, region_name=region)
        self.acm_client = self.session.client('acm')
        self.route_53_client = self.r53_session.client('route53')
        self.domain = domain

    def get_certificate_arn(self, response):
        """ Given an ACM Boto response,
            return the ACM Certificate ARN
        """
        return response.get('CertificateArn')

    def request_certificate(self, domain, subject_alternative_names=[]):
        """ Given a domain name and a list of subject alternative names,
            request a certificate and return the certificate ARN.
        """
        if len(subject_alternative_names) > 0:
            response = self.acm_client.request_certificate(
                DomainName=domain,
                ValidationMethod='DNS',
                SubjectAlternativeNames=subject_alternative_names)
        else:
            response = self.acm_client.request_certificate(
                DomainName=domain, ValidationMethod='DNS')

        if aws_helpers.response_succeeded(response):
            return self.get_certificate_arn(response)

    def get_certificate_status(self, certificate_arn):
        return self.acm_client.describe_certificate(CertificateArn=certificate_arn)['Certificate']['Status']

    def wait_for_certificate_validation(self, certificate_arn, sleep_time=5, timeout=600):

        status = self.get_certificate_status(certificate_arn)
        elapsed_time = 0
        while status == 'PENDING_VALIDATION':
            if elapsed_time > timeout:
                raise Exception('Timeout ({}s) reached for certificate validation'.format(timeout))
            print("{}: Waiting {}s for validation, {}s elapsed...".format(certificate_arn, sleep_time, elapsed_time))
            time.sleep(sleep_time)
            status = self.get_certificate_status(certificate_arn)
            elapsed_time += sleep_time

    def get_domain_validation_records(self, arn):
        """ Return the domain validation records from the describe_certificate
            call for our certificate
        """
        certificate_metadata = self.acm_client.describe_certificate(
            CertificateArn=arn)
        return certificate_metadata.get('Certificate', {}).get(
            'DomainValidationOptions', [])

    def get_hosted_zone_id(self):
        """ Return the HostedZoneId of the zone tied to the root domain
            of the domain the user wants to protect (e.g. given www.cnn.com, return cnn.com)
            if it exists in Route53. Else error.
        """

        def get_domain_from_host(domain):
            """ Given an FQDN, return the domain
                portion of a host
            """
            domain_tld_info = tldextract.extract(domain)
            return "%s.%s" % (domain_tld_info.domain, domain_tld_info.suffix)

        def domain_matches_hosted_zone(domain, zone):
            return zone.get('Name') == "%s." % (domain)

        def get_zone_id_from_id_string(zone_id_string):
            return zone_id_string.split('/')[-1]

        response = self.route_53_client.list_hosted_zones()
        hosted_zone_domain = get_domain_from_host(self.domain)
        target_record = list(
            filter(
                lambda zone: domain_matches_hosted_zone(hosted_zone_domain, zone),
                response.get('HostedZones')))

        return get_zone_id_from_id_string(target_record[0].get('Id'))

    def get_resource_record_data(self, r):
        """ Given a ResourceRecord dictionary from an ACM certificate response,
            return the type, name and value of the record
        """
        return (r.get('Type'), r.get('Name'), r.get('Value'))

    def create_dns_record_set(self, record):
        """ Given a HostedZoneId and a list of domain validation records,
            create a DNS record set to send to Route 53
        """
        record_type, record_name, record_value = self.get_resource_record_data(
            record.get('ResourceRecord'))
        print("Creating %s record for %s" % (record_type, record_name))

        return {
            'Action': 'UPSERT',
            'ResourceRecordSet': {
                'Name': record_name,
                'Type': record_type,
                'ResourceRecords': [{
                    'Value': record_value
                }],
                'TTL': 300,
            }
        }

    def create_domain_validation_records(self, arn):
        """ Given an ACM certificate ARN,
            return the response
        """
        domain_validation_records = self.get_domain_validation_records(arn)
        hosted_zone_id = self.get_hosted_zone_id()
        print("Hosted Zone ID: %s" % hosted_zone_id)

        names = set()
        changes = []
        for record in domain_validation_records:
            record_type, record_name, record_value = self.get_resource_record_data(
                record.get('ResourceRecord'))
            if(record_name not in names):
                changes.append(self.create_dns_record_set(record))
                names.add(record_name)
        response = self.route_53_client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id, ChangeBatch={
                'Changes': changes,
            })

        if aws_helpers.response_succeeded(response):
            print("Successfully created Route 53 record set")
