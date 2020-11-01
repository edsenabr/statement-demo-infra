#!/usr/bin/env python3
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_elasticsearch as es,
    aws_logs as logs,
    custom_resources as sdk,
    aws_secretsmanager as sm,
    core
)

class Elastic(core.Stack):
  def __init__(self, scope: core.Construct, id: str, VPC: ec2.Vpc, **kwargs) -> None:
    super().__init__(scope, id, **kwargs)
    elastic_policy = iam.PolicyStatement(
        effect=iam.Effect.ALLOW, actions=["es:*",], resources=["*"],
    )
    elastic_policy.add_any_principal()
    elastic_document = iam.PolicyDocument()
    elastic_document.add_statements(elastic_policy)

    appLog=logs.LogGroup(
      self, "appLog",
      log_group_name="/statement-demo/es/app",
      removal_policy=core.RemovalPolicy.DESTROY, 
      retention=logs.RetentionDays.ONE_WEEK
    )

    searchLog=logs.LogGroup(
      self, "searchLog",
      log_group_name="/statement-demo/es/search",
      removal_policy=core.RemovalPolicy.DESTROY, 
      retention=logs.RetentionDays.ONE_WEEK
    )

    indexLog=logs.LogGroup(
      self, "indexLog",
      log_group_name="/statement-demo/es/index",
      removal_policy=core.RemovalPolicy.DESTROY, 
      retention=logs.RetentionDays.ONE_WEEK
    )

    auditLog=logs.LogGroup(
      self, "auditLog",
      log_group_name="/statement-demo/es/audit",
      removal_policy=core.RemovalPolicy.DESTROY, 
      retention=logs.RetentionDays.ONE_WEEK
    )

    self.secret = sm.Secret(
      self,
      "masterUserSecret",
      generate_secret_string=sm.SecretStringGenerator(
        password_length=8,
        exclude_characters="\"#$%&'()*+,./:;<=>?[\\]^_`{|}~",
      ),
      removal_policy=core.RemovalPolicy.DESTROY,
    )

    self.domain = es.Domain(
      self,
      "elastic_domain",
      version=es.ElasticsearchVersion.V7_7, 
      access_policies=[elastic_policy],
      advanced_options=None, 
      capacity=es.CapacityConfig(
        data_node_instance_type=self.node.try_get_context("elastic")['instanceType'], 
        data_nodes=self.node.try_get_context("elastic")['instanceCount'], 
        master_node_instance_type=self.node.try_get_context("elastic")['master']['type'] if self.node.try_get_context("elastic")['master']['dedicated'] else None, 
        master_nodes=self.node.try_get_context("elastic")['master']['count'] if self.node.try_get_context("elastic")['master']['dedicated'] else None
      ), 
      domain_name="statement-demo", 
      ebs=es.EbsOptions(enabled=(not self.node.try_get_context("elastic")['instanceType'].startswith("i3"))), 
      encryption_at_rest=es.EncryptionAtRestOptions(enabled=True),
      enforce_https=True, 
      fine_grained_access_control = es.AdvancedSecurityOptions (
          master_user_name="admin",
          master_user_password=self.secret.secret_value
      ),
      logging=es.LoggingOptions(
        app_log_enabled=True, 
        app_log_group=appLog, 
        slow_index_log_enabled=True, 
        slow_index_log_group=indexLog, 
        slow_search_log_enabled=True, 
        slow_search_log_group=searchLog
      ), 
      node_to_node_encryption=True, 
      tls_security_policy=es.TLSSecurityPolicy.TLS_1_2, 
      use_unsigned_basic_auth=True, 
      vpc_options=es.VpcOptions(
        security_groups=[],
        subnets=VPC.private_subnets
      ), 
      zone_awareness=es.ZoneAwarenessConfig(
        availability_zone_count=3, 
        enabled=True
      )
    )