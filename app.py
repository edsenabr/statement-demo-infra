#!/usr/bin/env python3
from stacks.network import Network
from stacks.es import Elastic
from stacks.es_config import ElastiSearchConfig
from stacks.eks import Kubernetes
from stacks.eks_config import KubernetesConfig
from stacks.msk import Kafka
from stacks.msk_config import KafkaConfig
from stacks.uw import UltraWarm
import boto3 

from aws_cdk import (
  core
)

app = core.App()
usEast1 = core.Environment(account=boto3.client('sts').get_caller_identity().get('Account'), region="us-east-1")
tags = {"stack": "statement-demo"}
network = Network(app, "network", env=usEast1, tags=tags)
kafka = Kafka(app, "kafka", network.vpc, env=usEast1, tags=tags)
kubernetes = Kubernetes(app, "kubernetes", network.vpc, env=usEast1, tags=tags)
elastic = Elastic(app, "elastic", network.vpc, env=usEast1, tags=tags)
kubernetes_config = KubernetesConfig(app, "kubernetes-config", kubernetes.cluster, env=usEast1, tags=tags)
elastic_config = ElastiSearchConfig(app, "elastic-config", elastic, network.vpc, kubernetes_config.roles, kubernetes.cluster, env=usEast1, tags=tags)
KafkaConfig(app, "kafka-config", kubernetes.cluster, kafka.cluster, network.vpc, env=usEast1, tags=tags)
if (app.node.try_get_context("elastic")["warm"]["enabled"]):
  UltraWarm(app, "elastic-ultrawarm", elastic.domain, env=usEast1, tags=tags)
app.synth()