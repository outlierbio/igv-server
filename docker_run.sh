IMAGE=igv-server
docker build -t $IMAGE .

docker run \
	-p 80:5000 \
	-e AIRTABLE_API_KEY=$AIRTABLE_API_KEY \
	-e AIRTABLE_API_ENDPOINT=$AIRTABLE_API_ENDPOINT \
	-e S3_BUCKET=$S3_BUCKET \
	-e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
	-e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
	$IMAGE