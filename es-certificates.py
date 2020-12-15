#!/usr/bin/env python3
import boto3
import re
from OpenSSL import crypto
acm = boto3.client('acm')


class ESCertificates:
	cluster1=''
	cluster2=''
	def __init__(self) -> None:
		ca = create_ca()
		self.cluster1 = create_cert("cluster1", ca)
		self.cluster1 = create_cert("cluster2", ca)
		self.alb = create_cert("alb", ca)


class Certificate:
	cert = ''
	key = ''

	def __init__(self, cert: crypto.X509, key: crypto.PKey) -> None:
		self.cert = cert
		self.key = key

	def sign(self, key: crypto.PKey = None) -> None:
		self.cert.sign(
			key if key else self.key,
			digest="sha256"
		)


def create_base_cert(name: str, ca: crypto.X509 = None) -> Certificate:
	key = crypto.PKey()
	key.generate_key (type=crypto.TYPE_RSA, bits=2048)

	cert = crypto.X509()
	cert.set_version(0x2)
	cert.set_serial_number(1)
	cert.get_subject().commonName= name if ca else ("%s.elastic.extrato.dev.aws.cloud.ihf" % name)
	cert.set_pubkey(key)
	cert.set_issuer(
		ca.cert.get_subject() if ca
		else cert.get_subject()
	)
	cert.gmtime_adj_notBefore(0)
	cert.gmtime_adj_notAfter(365*24*60*60*10)
	return Certificate(cert, key)

def create_ca() -> Certificate: 
	ca = create_base_cert("CA")
	ca.cert.add_extensions([
			crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=ca.cert),
			crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE"),
			crypto.X509Extension(b"keyUsage", True, b"digitalSignature, keyCertSign, cRLSign")
	])
	ca.sign()
	cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, ca.cert)
	save_file("ca", "crt", cert_pem)
	return ca

def save_file(name: str, type: str, content: str) -> None:
	f = open(
		"%s.elastic.extrato.dev.aws.cloud.ihf.%s" % (name, type), 
		"w"
	)
	f.write(content.decode('utf-8'))
	f.close()

def create_cert(name: str, ca: crypto.X509) -> Certificate : 
	cert = create_base_cert(name, ca)
	cert.cert.add_extensions([
		crypto.X509Extension(b"subjectAltName", True, bytes(("DNS:%s.elastic.extrato.dev.aws.cloud.ihf" % name),"utf-8")),
		crypto.X509Extension(b"basicConstraints", True, b"CA:FALSE"),
		crypto.X509Extension(b"authorityKeyIdentifier", False, b"keyid:always,issuer", issuer=ca.cert),
		crypto.X509Extension(b"subjectKeyIdentifier", False, b"hash", subject=cert.cert),
		crypto.X509Extension(b"keyUsage", True, b"digitalSignature, keyEncipherment"),
		crypto.X509Extension(b"extendedKeyUsage", True, b"serverAuth, clientAuth")
	])
	cert.sign(ca.key)
	cert_pem = crypto.dump_certificate(crypto.FILETYPE_PEM, cert.cert)
	key_pem = crypto.dump_privatekey(crypto.FILETYPE_PEM, cert.key)
	save_file(name, "crt", cert_pem)
	save_file(name, "key", key_pem)
	return cert
	

	# return acm.import_certificate(
	# 	Certificate=cert_pem,
	# 	PrivateKey=key_pem,
	# 	CertificateChain=crypto.dump_certificate(crypto.FILETYPE_PEM, ca.cert),
	# 	Tags=[{
	# 		'Key': 'Name',
	# 		'Value': ('%s.elastic.extrato.dev.aws.cloud.ihf' % name)
	# 	}]
	# )['CertificateArn']



if __name__ == "__main__" :
	ESCertificates()