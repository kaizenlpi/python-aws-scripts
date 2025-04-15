''' SOP: 

1. You must authenticate to the correct region us-west-1 or us-east-1 using saml2aws credentials and yubikey. 
2. Obtain instance ID to enter as user input. 
3. Confirm /staging unmounted. 

--> TO DO: NOTE: Script does not comment out or delete the line with "/staging" yet. This works to comment out the line with /staging from the command line
sed -i '/[/]mymount/ s/^/#/' /etc/fstab 
But it is not working via the python script, yet. 

'''
#!/usr/bin/env python3
import sys
import boto3

def main():
    # Check if an instance ID is provided as a command-line argument.
    if len(sys.argv) == 2:
        instance_id = sys.argv[1]
    else:
        # Prompt the user for the instance ID if not provided.
        instance_id = input("Please enter the instance ID: ").strip()
        if not instance_id:
            print("Instance ID cannot be empty. Exiting.")
            sys.exit(1)

    # Create an SSM client.
    ssm_client = boto3.client('ssm')

    # The shell script executed on the instance does the following:
    # 1. Unmount the /staging directory.
    # 2. Create a backup of /etc/fstab as /etc/fstab.bak.
    # 3. Use an inline Python snippet to read /etc/fstab, delete any line containing "/staging",
    #    then write back the modified file.
    # 4. Print the contents of /etc/fstab and check for occurrences of "/staging" to confirm deletion.
    script = """#!/bin/bash
sudo umount /staging
sudo cp /etc/fstab /etc/fstab.bak
# Use Python to delete any line that contains "/staging" from /etc/fstab
sudo python3 - << 'EOF'
try:
    with open("/etc/fstab", "r") as f:
        lines = f.readlines()
    with open("/etc/fstab", "w") as f:
        for line in lines:
            if "/staging" not in line:
                f.write(line)
except Exception as e:
    print("Error processing /etc/fstab:", e)
    exit(1)
EOF
echo "Contents of /etc/fstab after deletion operation:"
sudo cat /etc/fstab
echo "Checking for '/staging' in /etc/fstab:"
sudo grep "/staging" /etc/fstab && echo "Found '/staging'" || echo "No '/staging' found"
"""

    # Send the multi-line script to the specified instance via AWS Systems Manager Run Command.
    response = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [script]}
    )

    # Print the command ID to confirm the command was sent.
    command_id = response['Command']['CommandId']
    print(f"Sent unmount and /etc/fstab update commands to instance {instance_id}.")
    print(f"Command ID: {command_id}")

if __name__ == "__main__":
    main()
