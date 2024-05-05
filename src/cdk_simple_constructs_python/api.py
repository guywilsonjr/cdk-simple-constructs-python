from typing import Optional

from aws_cdk import Environment, Stack
from aws_cdk.aws_apigatewayv2 import CorsPreflightOptions, DomainMappingOptions, DomainName, HttpApi
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from aws_cdk.aws_lambda import IFunction
from aws_cdk.aws_logs import LogGroup
from aws_cdk.aws_route53 import ARecord, IHostedZone, RecordTarget
from aws_cdk.aws_route53_targets import ApiGatewayv2DomainProperties
from constructs import Construct
from pydantic import BaseModel, model_validator
from cdk_simple_constructs_python.cert import Cert


class CertOptions(BaseModel):
    hosted_zone: IHostedZone


class ExistingCertOptions(CertOptions):
    existing_cert_arn: str


class DomainNameOptions(BaseModel):
    api_dns_name: str
    cert_options: CertOptions | ExistingCertOptions
    create_api_dns_record: bool = False

    @model_validator(mode='after')
    def validate_data(self):
        if self.create_api_dns_record:
            if not (self.api_dns_name or self.cert_options):
                raise ValueError('api_dns_name and cert_options must be provided if create_api_dns_record is True')
            elif not self.api_dns_name:
                raise ValueError('api_dns_name must be provided if create_api_dns_record is True')
            elif not self.cert_options:
                raise ValueError('cert_options must be provided if create_api_dns_record is True')
        if self.cert_options and not self.api_dns_name:
            raise ValueError('api_dns_name must be provided if cert_options is provided')
        if self.api_dns_name and not self.cert_options:
            raise ValueError('cert_options must be provided if api_dns_name is provided')


# noinspection PyAttributeOutsideInit
class API(Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env: Environment,
        api_function: IFunction,
        domain_name_options: Optional[DomainNameOptions] = None,
        cors_preflight_options: CorsPreflightOptions = CorsPreflightOptions(),
    ) -> None:
        super().__init__(scope, construct_id, env=env)
        # noinspection PyTypeChecker
        self.integ = HttpLambdaIntegration('APIIntegration', api_function)
        self.api_lg = LogGroup(self, 'APILogGroup')
        self.create_dn(domain_name_options)
        self.api = HttpApi(
            self,
            'API',
            default_integration=self.integ,
            cors_preflight=cors_preflight_options,
            default_domain_mapping=DomainMappingOptions(domain_name=self.dn) if self.dn else None,

        )

    def create_dn(self, domain_name_options: Optional[DomainNameOptions]):
        self.dn: Optional[DomainName] = None
        if domain_name_options:
            if isinstance(domain_name_options.cert_options, ExistingCertOptions):
                self.cert = Cert.from_arn(self, 'Cert', domain_name_options.cert_options.existing_cert_arn)
            else:
                self.cert_stack = Cert(
                    self,
                    'Cert',
                    hz=domain_name_options.cert_options.hosted_zone,
                    site_name=domain_name_options.api_dns_name,
                    cert_region=self.api.env.region,
                    cert_options=domain_name_options.cert_options
                )
                self.cert = self.cert_stack.cert

            self.dn = DomainName(
                self,
                'DomainName',
                domain_name=domain_name_options.api_dns_name,
                certificate=self.cert,
            )
            if domain_name_options.create_api_dns_record:
                api_dns_split = domain_name_options.api_dns_name.split('.')
                api_dns_prefix = '.'.join(api_dns_split[:-2])
                self.api_rec = ARecord(
                    self,
                    'Record',
                    record_name=api_dns_prefix,
                    region=self.api.env.region,
                    target=RecordTarget.from_alias(
                        ApiGatewayv2DomainProperties(
                            regional_domain_name=self.dn.regional_domain_name,
                            regional_hosted_zone_id=self.dn.regional_hosted_zone_id
                        )
                    ),
                    zone=domain_name_options.cert_options.hosted_zone
                )
