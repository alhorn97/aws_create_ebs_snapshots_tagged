import boto3
import collections
import datetime

ec = boto3.client('ec2')

def lambda_handler(event, context):
    reservations = ec.describe_instances(
        Filters=[
            {'Name': 'tag-key', 'Values': ['bkup', 'true']},
        ]
    ).get(
        'Reservations', []
    )

    instances = sum(
        [
            [i for i in r['Instances']]
            for r in reservations
        ], [])

    print "Found %d instances that need backing up" % len(instances)

    to_tag = collections.defaultdict(list)

    for instance in instances:
        try:
            retention_days = [
                int(t.get('Value')) for t in instance['Tags']
                if t['Key'] == 'Retention'][0]
        except IndexError:
            retention_days = 7

        for dev in instance['BlockDeviceMappings']:
            if dev.get('Ebs', None) is None:
                continue
            vol_id = dev['Ebs']['VolumeId']
            print "Found EBS volume %s on instance %s" % (
                vol_id, instance['InstanceId'])

            tag_purpose_test = {"Key": "Purpose", "Value": "Test"}
            
            snap = ec.create_snapshot(
                VolumeId=vol_id
                #tags=[{'ResourceType': 'instance','Tags': [tag_purpose_test]}])[0]
            )

            to_tag[retention_days].append(snap['SnapshotId'])

            print "Retaining snapshot %s of volume %s from instance %s for %d days" % (
                snap['SnapshotId'],
                vol_id,
                instance['InstanceId'],
                retention_days,
            )

            snapshot_name = 'N/A'
            if 'Tags' in instance:
                for tags in instance['Tags']:
                    if tags["Key"] == 'Name':
                        snapshot_name = tags["Value"]

            print "Tagging snapshot with Name: %s" % (snapshot_name)

            ec.create_tags(
                Resources=[
                    snap['SnapshotId'],
                ],
                Tags=[
                    {'Key': 'Name', 'Value': snapshot_name},
                    {'Key': 'Description', 'Value': "Created by lambda automated backups"},
                    {'Key': 'DRcopy', 'Value': "Required"}
                ]
            )




    for retention_days in to_tag.keys():
        delete_date = datetime.date.today() + datetime.timedelta(days=retention_days)
        delete_fmt = delete_date.strftime('%Y-%m-%d')
        print "Will delete %d snapshots on %s" % (len(to_tag[retention_days]), delete_fmt)
        ec.create_tags(
            Resources=to_tag[retention_days],
            Tags=[
                {'Key': 'DeleteOn', 'Value': delete_fmt},
            ]
        )