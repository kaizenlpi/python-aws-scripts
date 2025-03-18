import boto3
import pprint

# List of AWS Regions
AWS_REGIONS = ["us-gov-west-1", "us-gov-east-1"]

# Iterate through each AWS Region
for region in AWS_REGIONS:
    print(f"Checking region: {region}")
    
    # Create EC2 client for the specific region
    ec2_client = boto3.client('ec2', region_name=region)

    # Describe available volumes
    try:
        response = ec2_client.describe_volumes(
            Filters=[{'Name': 'status', 'Values': ['available']}]
        )
    except Exception as e:
        print(f"Error fetching volumes in {region}: {e}")
        continue  # Move to the next region if there's an error

    # Print available volumes
    available_volumes = response.get('Volumes', [])
    if not available_volumes:
        print(f"No available volumes found in {region}.")
        continue

    print(f"Available EBS Volumes in {region}:")
    pprint.pprint(available_volumes)

    # Iterate and delete volumes
    for volume in available_volumes:
        volume_id = volume['VolumeId']
        try:
            print(f"Deleting Volume: {volume_id} in {region}")
            ec2_client.delete_volume(VolumeId=volume_id)
            print(f"✅ Volume {volume_id} deleted successfully.")
        except Exception as e:
            print(f"❌ Failed to delete {volume_id}: {e}")
