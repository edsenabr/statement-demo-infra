#!/usr/bin/env python3
from .certs import MTLSCertificates
from aws_cdk import (
    aws_ec2 as ec2,
    core
)

class Network(core.Stack):
  def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
    super().__init__(scope, id, **kwargs)

    self.vpc = ec2.Vpc(
      self, 
      "vpc",
      cidr=self.node.try_get_context("vpc")["cidr"],
      max_azs=3,
      nat_gateways=1
    )

    certs = MTLSCertificates()

    vpn = ec2.CfnClientVpnEndpoint(
      self, 
      "vpn",
      authentication_options=[
        ec2.CfnClientVpnEndpoint.ClientAuthenticationRequestProperty(
          type="certificate-authentication",
          mutual_authentication=ec2.CfnClientVpnEndpoint.CertificateAuthenticationRequestProperty(
            client_root_certificate_chain_arn=certs.client
          )

        )
      ],
      client_cidr_block=self.node.try_get_context("vpc")["client_cidr_block"],
      connection_log_options={
        "enabled" : False
      },
      server_certificate_arn=certs.server,
      split_tunnel=True,
      vpc_id=self.vpc.vpc_id
    )

    for subnet in self.vpc.private_subnets: 
      ec2.CfnClientVpnTargetNetworkAssociation(
        self, 
        "Associations%s" % subnet.node.id,
        client_vpn_endpoint_id=vpn.ref,
        subnet_id=subnet.subnet_id
      )
    core.CfnOutput(
      self,
      "VPNEndpoint",
      value = "%s.%s.prod.clientvpn.%s.amazonaws.com" % (  core.Stack.of(self).stack_name, vpn.ref, core.Stack.of(self).region)
    )

    ec2.CfnClientVpnAuthorizationRule(
        self, 
        "VPNAuth",
        client_vpn_endpoint_id=vpn.ref,
        target_network_cidr=self.vpc.vpc_cidr_block,
        authorize_all_groups=True
    )
