from typing import Optional

from aws_cdk import Environment, Stack
from aws_cdk.aws_certificatemanager import Certificate, CertificateValidation

from aws_cdk.aws_route53 import IHostedZone


class Cert(Stack):

    def __init__(
        self,
        app: Stack,
        stack_id: str,
        env: Environment,
        hz: IHostedZone,
        site_name: str,
        cert_region: Optional[str] = None,
    ) -> None:
        if not cert_region:
            cert_region = env.region
        super().__init__(app, stack_id, env=Environment(account=env.account, region=cert_region))
        self.cert = Certificate(
            self,
            'Cert',
            domain_name=site_name,
            validation=CertificateValidation.from_dns(hz))


