# Author: Matt Brady
# Date: 3/7/25 

import boto3

AWS_REGION = "us-gov-west-1"
ec2 = boto3.client('ec2', region_name = AWS_REGION)

# Initialize AWS clients
ec2_client = boto3.client('ec2')
pricing_client = boto3.client('pricing', region_name=AWS_REGION)  # Pricing API is in us-gov-west-1

# Get all EBS volumes
response = ec2_client.describe_volumes()

# Fetch EBS pricing
pricing_response = pricing_client.get_products(
    ServiceCode='AmazonEC2',
    Filters=[
        {'Type': 'TERM_MATCH', 'Field': 'productFamily', 'Value': 'Storage'},
        {'Type': 'TERM_MATCH', 'Field': 'volumeType', 'Value': 'General Purpose'},  # Change as needed
    ]
)

# Extract price per GB-month
price_json = pricing_response['PriceList'][0]
import json
price_data = json.loads(price_json)
price_per_gb = float(
    list(price_data['terms']['OnDemand'].values())[0]['priceDimensions'].values().__iter__().__next__()['pricePerUnit']['USD']
)

# Calculate and display cost for each volume
total_cost = 0
print("EBS Volume Costs:")
for volume in response['Volumes']:
    volume_size = volume['Size']  # Size in GB
    volume_cost = volume_size * price_per_gb
    total_cost += volume_cost
    print(f"Volume ID: {volume['VolumeId']}, Size: {volume_size} GiB, Estimated Cost: ${volume_cost:.2f}/month")

print(f"\nTotal Estimated Monthly Cost: ${total_cost:.2f}")
