#!/usr/bin/env python3
import boto3
ecr = boto3.client('ecr')

def handler(event, context):
	print("*** called with event=%s ***" % event)
	action = event['RequestType']
	repository = event['ResourceProperties']['repository']

	if action != "Delete":
		return {
			'statusCode': 200
		}		
		
	images = ecr.describe_images(
		repositoryName=repository,
		maxResults=1000,
		filter={
			'tagStatus': 'ANY'
    }
	)

	imageIds=[]
	for image in images['imageDetails']:
		imageIds.append({
			"imageDigest": image['imageDigest']
		})

	if len(imageIds) > 0:
		ecr.batch_delete_image(
			repositoryName=repository,
			imageIds=imageIds
		)

	return {
		'statusCode': 200
	}		
