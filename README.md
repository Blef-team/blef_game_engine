# Game engine service for `Blef`
> The API service to create manage and run games of Blef

This repository contains the code to run the Blef game engine API service.

At the initial stage it consists of a few basic endpoints, to create, join, start and run a game.

Game states are currently stored in and retrieved from `.rds` files. When necessary, this data will be migrated to an appropriate database, which will run alongside the API, or on separate infrastructure.

The service is deployed to EC2 with CodeDeploy integration.


## Deployment

#### Single deployment
To execute a single deployment, run the following command:
```
aws deploy create-deployment \
>   --application-name GameEngineService \
>   --deployment-config-name CodeDeployDefault.OneAtATime \
>   --deployment-group-name GameEngineService-DeploymentGroup \
>   --description "DEPLOYMENT DESCRIPTION" \
>   --github-location repository=maciej-pomykala/blef_game_engine,commitId=<COMMIT ID>
```
which returns a deployment id.
To check the deployment status:
```
aws deploy get-deployment --deployment-id <DEPLOYMENT ID> --query "deploymentInfo.status" --output text
```

#### Setting up new deployment integration
To set up EC2/CodeDeploy integration from scratch, follow these steps (__change resource names__):

Create an instance profile:
```
aws iam create-instance-profile --instance-profile-name CodeDeploy-EC2-Instance-Profile
```
Create a role for the instance profile:
```
aws iam create-role --role-name CodeDeploy-EC2-Instance-Profile --assume-role-policy-document file://<PATH TO REPO>/deployment/CodeDeploy-EC2-Trust.json
```
Add permissions to the role:
```
aws iam put-role-policy --role-name CodeDeploy-EC2-Instance-Profile --policy-name CodeDeploy-EC2-Permissions --policy-document file://<PATH TO REPO>/deployment/CodeDeploy-EC2-Permissions.json
```
Add the role to the new instance profile:
```
aws iam add-role-to-instance-profile --instance-profile-name CodeDeploy-EC2-Instance-Profile --role-name CodeDeploy-EC2-Instance-Profile
```
Attached the instance profile to the EC2 instance:
```
aws ec2 associate-iam-instance-profile --iam-instance-profile Name=CodeDeploy-EC2-Instance-Profile --instance-id=<INSTANCE ID>
```
Tagged the instance:
```
aws ec2 create-tags --resources <INSTANCE ID> --tags Key=name,Value=GameEngineServer
```
Create a CodeDeploy application:
```
aws deploy create-application --application-name GameEngineService
```
Create a CodeDeploy deployment group:
```
aws deploy create-deployment-group --application-name GameEngineService --ec2-tag-filters Key=ec2-tag-key,Type=KEY_AND_VALUE,Value=GameEngineServer --deployment-group-name GameEngineService-DeploymentGroup --service-role-arn arn:aws:iam::<ACCOUNT ID>:role/CodeDeployServiceRole
```
