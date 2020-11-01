#!/usr/bin/env python3
from aws_cdk import (
		aws_eks as eks,
		aws_ec2 as ec2,
		aws_iam as iam,
		core
)
import boto3 
import requests
import yaml

class Kubernetes(core.Stack):

	def __init__(self, scope: core.Construct, id: str, VPC: ec2.Vpc, **kwargs) -> None:
		super().__init__(scope, id, **kwargs)

		cluster_admin = iam.Role(self, "AdminRole",
			assumed_by=iam.AccountRootPrincipal()
		)

		self.cluster = eks.Cluster(
			self, 
			"cluster",
			default_capacity=self.node.try_get_context("kubernetes")["default_capacity"],
			default_capacity_instance=ec2.InstanceType(self.node.try_get_context("kubernetes")["default_capacity_instance"]),
			cluster_name="statement-demo",
			vpc=VPC,
			vpc_subnets = VPC.private_subnets,
			masters_role=cluster_admin,
			version=eks.KubernetesVersion.V1_17,
			endpoint_access=eks.EndpointAccess.PRIVATE
		)

		vpc_security_group=ec2.SecurityGroup.from_security_group_id(self, "sgVPC", VPC.vpc_default_security_group)
		eks_security_group=ec2.SecurityGroup.from_security_group_id(self, "sgEKS", self.cluster.cluster_security_group_id)

		vpc_security_group.add_ingress_rule(
			eks_security_group,
			ec2.Port.all_traffic()
		)

		eks_security_group.add_ingress_rule(
			vpc_security_group,
			ec2.Port.all_traffic()
		)

		self.cluster.default_nodegroup.role.add_managed_policy(
			iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchAgentServerPolicy")
		)


		#see https://github.com/kubernetes/kubernetes/issues/61486?#issuecomment-635169272
		eks.KubernetesPatch(
			self,
			"patch",
			cluster=self.cluster,
			resource_name="daemonset/kube-proxy",
			resource_namespace="kube-system",
			apply_patch = {
				"spec": {
					"template": {
						"spec": {
							"containers": [{
								"name": "kube-proxy",
								"command": [
										"kube-proxy",
										"--v=2",
										"--hostname-override=$(NODE_NAME)",
										"--config=/var/lib/kube-proxy-config/config",
								],
								"env": [{
									"name": "NODE_NAME",
									"valueFrom": {
										"fieldRef": {
											"apiVersion": "v1",
											"fieldPath": "spec.nodeName"
										}
									}
								}]
							}]
						}
					}
				}
			},
			restore_patch={
				"spec": {
					"template": {
						"spec": {
							"containers": [{
								"name": "kube-proxy",
								"command": [
									"kube-proxy",
									"--v=2",
									"--config=/var/lib/kube-proxy-config/config"
								]
							}]
						}
					}
				}
			}
		)

		# elasticsearch clusters has many nodes, and its DNS records are always truncated by OpenDNS
		eks.KubernetesPatch(
			self,
			"coreDNSTCP",
			cluster=self.cluster,
			resource_name="configmap/coredns",
			resource_namespace="kube-system",
			apply_patch={
				"data": {
						"Corefile": ".:53 {\n    errors\n    health\n    kubernetes cluster.local in-addr.arpa ip6.arpa {\n      pods insecure\n      upstream\n      fallthrough in-addr.arpa ip6.arpa\n    }\n    prometheus :9153\n    forward . /etc/resolv.conf {\n      force_tcp\n    }\n    cache 30\n    loop\n    reload\n    loadbalance\n}\n"
				}
			},
			restore_patch={
				"data": {
						"Corefile": ".:53 {\n    errors\n    health\n    kubernetes cluster.local in-addr.arpa ip6.arpa {\n      pods insecure\n      upstream\n      fallthrough in-addr.arpa ip6.arpa\n    }\n    prometheus :9153\n    forward . /etc/resolv.conf\n    cache 30\n    loop\n    reload\n    loadbalance\n}\n"
				}
			}
		)

		# adding myself as a cluster admin
		self.cluster.aws_auth.add_user_mapping(
			iam.User.from_user_name(
				self, "me",
				boto3.client('sts').get_caller_identity().get('Arn').partition('/')[2]
			), 
			groups=["system:masters"]
		)

		text = requests.get(
			"https://raw.githubusercontent.com/aws-samples/amazon-cloudwatch-container-insights/latest/k8s-deployment-manifest-templates/deployment-mode/daemonset/container-insights-monitoring/quickstart/cwagent-fluentd-quickstart.yaml"
		).text.replace(
			"{{cluster_name}}", 
			self.cluster.cluster_name
		).replace(
			"{{region_name}}", 
			core.Stack.of(self).region
		)
		eks.KubernetesManifest(
			self, 
			"containerInsights", 
			cluster=self.cluster, 
			manifest=[yaml.load(item) for item in text.split("---\n")]
		)