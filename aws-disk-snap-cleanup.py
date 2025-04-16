import time
import boto3
from datetime import datetime, timedelta
from botocore.exceptions import ClientError
import csv
import os

# AWS Client creation for EC2
def create_clients(region, session):
    return session.client('ec2', region_name=region)

# Discover detached AWS volumes
def find_aws_detached_volumes(ec2_client):
    print('\n## Locating unattached volumes in AWS ##')
    volumes_data = []
    try:
        response = ec2_client.describe_volumes(Filters=[{'Name': 'status', 'Values': ['available']}])
        volumes = response.get('Volumes', [])
    except Exception as e:
        print(f"Error fetching volumes: {e}")
        return volumes_data

    if not volumes:
        print("No unattached volumes found in this region.")
    for volume in volumes:
        volume_info = {
            "Region": ec2_client.meta.region_name,
            "Volume ID": volume['VolumeId'],
            "Size (GiB)": volume['Size'],
            "Availability Zone": volume['AvailabilityZone'],
            "Created On": volume['CreateTime'],
            "Volume Type": volume['VolumeType'],
            "Tags": volume.get('Tags', [])
        }
        print(f"Volume ID: {volume_info['Volume ID']} - Size: {volume_info['Size (GiB)']} GiB - AZ: {volume_info['Availability Zone']}")
        volumes_data.append(volume_info)
    return volumes_data

# Calculate the monthly cost of a volume
def calculate_monthly_cost(volume_type, size_gb, region):
    pricing = {
        "gp2": 0.10,
        "gp3": 0.08,
        "io1": 0.125,
        "io2": 0.125,
        "st1": 0.045,
        "sc1": 0.025,
    }
    return size_gb * pricing.get(volume_type, 0.0)

# ❗️New function: Delete AWS volume
def delete_volume(ec2_client, volume_id):
    try:
        ec2_client.delete_volume(VolumeId=volume_id)
        print(f"🗑️ Volume {volume_id} deleted successfully.")
        return "Deleted"
    except ClientError as e:
        print(f"❌ Failed to delete volume {volume_id}: {e}")
        return f"Delete Failed: {e.response['Error']['Message']}"

# Create snapshots for detached volumes
def make_aws_disk_snapshots(all_detached_volumes, ec2_client, date_plus_10):
    print('\n\n## Creating AWS disk snapshots for unattached volumes ##')
    data_snap_results = {}

    now = datetime.now()
    date = f"{now.month:02d}{now.day:02d}{str(now.year)[-2:]}"  # MMDDYY format

    for volume in all_detached_volumes:
        volume_id = volume['Volume ID']
        raw_tags = volume.get('Tags', [])

        # Default to volume_id
        volume_name = volume_id

        if isinstance(raw_tags, list):
            name_tag = next((tag['Value'] for tag in raw_tags if tag.get('Key', '').lower() == 'name'), None)
            instance_tag = next((tag['Value'] for tag in raw_tags if tag.get('Key', '').lower() == 'instance'), None)

            if name_tag:
                volume_name = name_tag
            elif instance_tag:
                volume_name = instance_tag

        # Sanitize volume_name
        volume_name_clean = volume_name.replace(" ", "_").replace("/", "-")

        print(f"🔍 Volume ID: {volume_id} - Using volume name: {volume_name_clean}")

        snap_name = f"{volume_name_clean}_{date}"

        volume['Volume Name'] = volume_name_clean
        volume['Snapshot Name'] = snap_name
        volume['Snapshot Deletion Date'] = date_plus_10

        try:
            snapshot = ec2_client.create_snapshot(
                VolumeId=volume_id,
                Description=f"Snapshot of {snap_name}",
                TagSpecifications=[{
                    'ResourceType': 'snapshot',
                    'Tags': [
                        {'Key': 'Name', 'Value': snap_name},
                        {'Key': 'Purpose', 'Value': 'Backup'},
                        {'Key': 'Deletion_date', 'Value': date_plus_10}
                    ]
                }]
            )

            print(f"✅ Snapshot creation initiated for volume {volume_id} (Snapshot Name: {snap_name}). Snapshot ID: {snapshot['SnapshotId']}")

            data_snap_results[volume_id] = {
                'snap_name': snap_name,
                'snap_status': 'In Progress',
                'snapshot_id': snapshot['SnapshotId'],
                'snapshot_deletion_date': date_plus_10
            }

            # Wait for snapshot to complete
            snapshot_id = snapshot['SnapshotId']
            while True:
                try:
                    response = ec2_client.describe_snapshots(SnapshotIds=[snapshot_id])
                    snapshot_status = response['Snapshots'][0]['State']
                    print(f"Snapshot {snapshot_id} status: {snapshot_status}")

                    if snapshot_status != 'pending':
                        data_snap_results[volume_id]['snap_status'] = snapshot_status
                        break
                    time.sleep(10)
                except ClientError as e:
                    print(f"❌ Error checking snapshot status for {snapshot_id}: {e}")
                    break

            # ❗️Delete volume after snapshot creation
            delete_status = delete_volume(ec2_client, volume_id)
            volume['Volume Deletion Status'] = delete_status

        except ClientError as e:
            print(f"❌ Error creating snapshot for volume {volume_id}: {e}")
            data_snap_results[volume_id] = {
                'snap_name': snap_name,
                'snap_status': 'Failed',
                'snapshot_id': None,
                'snapshot_deletion_date': date_plus_10
            }
            volume['Volume Deletion Status'] = "Snapshot Failed - Not Deleted"

    return data_snap_results

# Save volumes to CSV with snapshot and deletion info
def save_volumes_to_csv(volumes, filename):
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = [
            'Region', 'Volume ID', 'Size (GiB)', 'Availability Zone', 'Created On',
            'Volume Type', 'Monthly Cost', 'Volume State', 'Customer', 'Volume Name',
            'Snapshot Name', 'Snapshot Deletion Date', 'Volume Deletion Status'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for vol in volumes:
            tags_list = vol.get('Tags', [])
            tags = {tag['Key']: tag['Value'] for tag in tags_list if isinstance(tag, dict)}

            writer.writerow({
                'Region': vol['Region'],
                'Volume ID': vol['Volume ID'],
                'Size (GiB)': vol['Size (GiB)'],
                'Availability Zone': vol['Availability Zone'],
                'Created On': vol['Created On'],
                'Volume Type': vol['Volume Type'],
                'Monthly Cost': calculate_monthly_cost(vol['Volume Type'], vol['Size (GiB)'], vol['Region']),
                'Volume State': 'available',
                'Customer': tags.get('Customer', 'N/A'),
                'Volume Name': tags.get('Name', 'N/A'),
                'Snapshot Name': vol.get('Snapshot Name', 'N/A'),
                'Snapshot Deletion Date': vol.get('Snapshot Deletion Date', 'N/A'),
                'Volume Deletion Status': vol.get('Volume Deletion Status', 'Not Attempted')
            })

# ---------------- Main Execution ----------------
if __name__ == "__main__":
    profile = "s4-cre-pce-g"
    session = boto3.Session(profile_name=profile)
    aws_gov_regions = ["us-gov-west-1", "us-gov-east-1"]
    all_detached_volumes = {}

    output_folder = os.path.join(os.getcwd(), "output")
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    current_date = datetime.now().strftime("%m%d%y")
    csv_filename = os.path.join(output_folder, f"aws_detached_volumes_{current_date}.csv")
    date_plus_10 = (datetime.now() + timedelta(days=10)).strftime("%m%d%y")

    for region in aws_gov_regions:
        print(f"\n### Checking region: {region} ###")
        ec2_client = create_clients(region, session)
        volumes = find_aws_detached_volumes(ec2_client)
        if volumes:
            snapshot_results = make_aws_disk_snapshots(volumes, ec2_client, date_plus_10)
            for vol in volumes:
                snap_info = snapshot_results.get(vol['Volume ID'], {})
                vol['Snapshot Name'] = snap_info.get('snap_name', 'N/A')
                vol['Snapshot Deletion Date'] = snap_info.get('snapshot_deletion_date', 'N/A')
                vol.setdefault('Volume Deletion Status', 'Not Attempted')
            all_detached_volumes[region] = volumes
        else:
            print(f"No volumes found in {region}")

    # Flatten and write to CSV
    flattened = [v for region_vols in all_detached_volumes.values() for v in region_vols]
    if flattened:
        save_volumes_to_csv(flattened, csv_filename)
        print(f"\n✅ CSV report saved at: {csv_filename}")
    else:
        print("\n✅ No data to write to CSV. Exiting.")

    print("\n🎉 Script completed.")
