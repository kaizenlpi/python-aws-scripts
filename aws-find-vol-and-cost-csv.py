import time
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import csv

# AWS Client creation for EC2
def create_clients(region, session):
    ec2_client = session.client('ec2', region_name=region)
    return ec2_client

# Discover detached AWS volumes
def find_aws_detached_volumes(ec2_client):
    print('\n## Locating unattached volumes in AWS ##')
    all_detached_volumes = []
    try:
        response = ec2_client.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
        print("Volumes discovered:")
    except Exception as e:
        print(f"Error fetching volumes: {e}")
        return all_detached_volumes  # Return empty list if there's an error

    volumes = response.get('Volumes', [])
    if not volumes:
        print("No unattached volumes found in this region.")
    for volume in volumes:
        volume_info = {
            "Region": ec2_client.meta.region_name,
            "Volume ID": volume['VolumeId'],
            "Size (GiB)": volume['Size'],
            "Availability Zone": volume['AvailabilityZone'],
            "Created On": volume['CreateTime'],
            "Volume Type": volume['VolumeType']  # Add Volume Type for cost calculation
        }
        print(f"Volume ID: {volume_info['Volume ID']} - Size: {volume_info['Size (GiB)']} GiB - Availability Zone: {volume_info['Availability Zone']}")
        all_detached_volumes.append(volume_info)
    return all_detached_volumes

# Calculate the monthly cost of a volume
def calculate_monthly_cost(volume_type, size_gb, region):
    pricing = {
        "gp2": 0.10,  # $ per GB per month
        "gp3": 0.08,  # $ per GB per month
        "io1": 0.125,  # $ per GB per month
        "io2": 0.125,  # $ per GB per month
        "st1": 0.045,  # $ per GB per month
        "sc1": 0.025,  # $ per GB per month
    }

    # Assuming all regions have similar pricing; if needed, you can adjust by region.
    if volume_type in pricing:
        cost_per_gb = pricing[volume_type]
        monthly_cost = size_gb * cost_per_gb
        return monthly_cost
    else:
        print(f"Unknown volume type: {volume_type}, assuming $0 cost.")
        return 0.0

# Make AWS disk snapshots (with retry and status check)
def make_aws_disk_snapshots(all_detached_volumes, ec2_client, date_plus_10):
    print('\n\n## Make AWS disk snapshot of unattached volumes ##')
    data_snap_results = {}

    # Current date (used for snapshot naming)
    now = datetime.now()
    date = f"{now.month:02d}{now.day:02d}{str(now.year)[-2:]}"  # MMDDYY format

    for volume in all_detached_volumes:
        volume_id = volume['Volume ID']
        print(f"Attempting to create snapshot for volume {volume_id}...")

        # Skip the describe_volumes check since we've already discovered these volumes
        snap_name = f"{volume_id}_{date}"

        try:
            # Create snapshot directly
            snapshot = ec2_client.create_snapshot(
                VolumeId=volume_id,
                Description="Snapshot for detached disk",
                TagSpecifications=[{
                    'ResourceType': 'snapshot',
                    'Tags': [
                        {'Key': 'Name', 'Value': snap_name},
                        {'Key': 'Purpose', 'Value': 'Backup'},
                        {'Key': 'DeleteAfter', 'Value': 'This Snapshot Will Be Deleted'},
                        {'Key': 'Deletion_date', 'Value': date_plus_10}  # Adding the Deletion date tag
                    ]
                }]
            )

            print(f"Snapshot creation initiated for volume {volume_id}. Snapshot ID: {snapshot['SnapshotId']}")

            # Log snapshot status as In Progress
            data_snap_results[volume_id] = {
                'snap_name': snap_name,
                'snap_status': 'In Progress',
                'snapshot_id': snapshot['SnapshotId']
            }

            # While loop to check if snapshot is still in progress
            snapshot_id = snapshot['SnapshotId']
            while True:
                try:
                    # Describe snapshot to check its status
                    response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
                    snapshot_status = response['Snapshots'][0]['State']

                    print(f"Snapshot {snapshot_id} status: {snapshot_status}")

                    if snapshot_status != 'pending':  # If snapshot is no longer in 'pending' state
                        # Update status and exit loop
                        data_snap_results[volume_id]['snap_status'] = snapshot_status
                        break
                    
                    # If still in progress, wait a bit and retry
                    time.sleep(10)  # Wait 10 seconds before checking again

                except ClientError as e:
                    print(f"❌ Error checking snapshot status for {snapshot_id}: {e}")
                    break

            # Delete volume after snapshot completion
            if data_snap_results[volume_id]['snap_status'] == 'completed':
                try:
                    print(f"Snapshot {snapshot_id} completed. Deleting volume {volume_id}...")
                    ec2_client.delete_volume(VolumeId=volume_id)
                    print(f"Volume {volume_id} successfully deleted.")
                    data_snap_results[volume_id]['volume_deleted'] = True
                except ClientError as e:
                    print(f"❌ Error deleting volume {volume_id}: {e}")
                    data_snap_results[volume_id]['volume_deleted'] = False

        except ClientError as e:
            # Log errors specific to this volume and continue
            print(f"❌ Error creating snapshot for volume {volume_id}: {e}")
            data_snap_results[volume_id] = {
                'snap_name': snap_name,
                'snap_status': 'Failed',
                'snapshot_id': None,
                'volume_deleted': False
            }

    return data_snap_results


# Save volume details including costs to CSV
def save_volumes_to_csv(all_detached_volumes, filename):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['Region', 'Volume ID', 'Size (GiB)', 'Availability Zone', 'Created On', 'Volume Type', 'Monthly Cost']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for volume in all_detached_volumes:
            volume_type = volume['Volume Type']
            size_gb = volume['Size (GiB)']
            region = volume['Region']
            monthly_cost = calculate_monthly_cost(volume_type, size_gb, region)
            volume['Monthly Cost'] = monthly_cost
            writer.writerow(volume)


# Main Execution
if __name__ == "__main__":
    # AWS profile and region list
    profile = "s4-cre-pce-g"
    session = boto3.Session(profile_name=profile)
    aws_gov_regions = ["us-gov-west-1", "us-gov-east-1"]
    all_detached_volumes = {}

    # Discover and gather detached volumes from each region
    for region in aws_gov_regions:
        all_detached_volumes[region] = []
        print(f"\n## Working with region: {region} ##")
        ec2_client = create_clients(region, session)
        detached_volumes_in_region = find_aws_detached_volumes(ec2_client)
        all_detached_volumes[region].extend(detached_volumes_in_region)

    # If no detached volumes are found, print a message and exit
    if not any(all_detached_volumes.values()):
        print("No detached volumes found in any region.")
    else:
        # Save volume details to CSV
        csv_filename = "detached_volumes_details.csv"
        save_volumes_to_csv([vol for vols in all_detached_volumes.values() for vol in vols], csv_filename)
        print(f"Volume details saved to {csv_filename}")

        # Snapshot creation
        date_plus_10 = (datetime.now() + timedelta(days=10)).strftime("%m%d%y")
        all_snapshots_results = {}
        
        # For each region, process the detached volumes and create snapshots
        for region, detached_volumes in all_detached_volumes.items():
            print(f"\nProcessing snapshots for region: {region}")
            ec2_client = create_clients(region, session)
            snapshot_creation_results = make_aws_disk_snapshots(detached_volumes, ec2_client, date_plus_10)
            all_snapshots_results[region] = snapshot_creation_results
        
        print(f"\nSnapshot creation and volume deletion results: {all_snapshots_results}")

    print('\nCompleted')
