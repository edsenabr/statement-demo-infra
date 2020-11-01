#!/usr/bin/env python3
from aws_cdk import (
    aws_ec2 as ec2,
    aws_msk as msk,
    core
)

class Kafka (core.Stack):
  def __init__(self, scope: core.Construct, id: str, VPC: ec2.Vpc, **kwargs) -> None:
    
    super().__init__(scope, id, **kwargs)

    self.cluster = msk.CfnCluster(
      self,
      "statement_kafka",
      cluster_name="statement-demo",
      broker_node_group_info = {
        "clientSubnets" : [subnet.subnet_id for subnet in VPC.private_subnets],
        "instanceType": self.node.try_get_context("kafka")["instanceType"],
        "storageInfo" : {
          "ebsStorageInfo" : {
            "volumeSize": self.node.try_get_context("kafka")["volumeSize"]
          }
        }
      },
      kafka_version="2.5.1",
      number_of_broker_nodes=self.node.try_get_context("kafka")["number_of_broker_nodes"],
      encryption_info={
        "encryptionInTransit": {
          "clientBroker": "TLS"
        }
      },
      enhanced_monitoring="PER_TOPIC_PER_BROKER"
    )