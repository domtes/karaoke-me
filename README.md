# Karaoke tracks from normal songs/videos

I'm going to play with [spleeter][https://github.com/deezer/spleeter]
to explore ideas around home/portable karaoke station for modern times.

It works! I can obtain an mp3 file with only the music, ready to sing over.

## Putting it on the cloud

To turn this into anything useful it would be nice to have the following:

- a simple domain (like deepkaraoke.me)
- an intuitive interface. You drop a file or a link to a video and the process starts.
  When it's done it turns into a link, ready to share.
- the conversion process should run on a serverless engine (AWS possibly)
- the frontend should be distributed via a CDN

After a failed attempt in packaging spleeter for lambda, I looked for viable  alternatives.

The most promising solution for running a custom docker container on demand (scaling from and to 0 instances), is AWS Batch.

1. You need to *define a job*
  - a name
  - a role
  - container image
  - command
  - vcpus (1 vcpu is equivalent to 1024 CPU shares)
  - memory (hard limit)
  - job attempts
  - parameters (if used in command definition)
  - environment variables

2. Configure the *compute environment* and *job queue*

you submit your jobs to a job queue that stores jobs until the AWS Batch scheduler runs the job on a compute resource within your compute environment.

- compute environment name, specify a unique name for the compute environment
- for Service Role, choose to create a new role that allows the AWS Batch service to make calls to the required AWS APIs on your behalf. (AWSBatchServiceRole is required).
- a job queue name

I've managed to build my simple collaboration of components for this kind of tasks, using AWS Batch.
The service allows to run batch jobs with a custom docker image, submitting the job instances with a simple API call.
I'm using docker hub, since my project will be open source. A realistic example should include ECR (a docker privare registry) for hosting images.

Now I need a lambda function to submit a new job for each new audio file being created in the input S3 bucket.

  S3 bucket -> event -> trigger_function -> AWS Batch job submitted

### What does not work with this approach

AWS Batch imposes *strict* requirements for memory allocation. If your process exceeds
that memory amount, the job gets instantly killed.
You can solve this allocating more resources in the computing environment, but I've noticed that doing so, the job will be less likely to be selected for execution in a 
timely fashion (my experiments easily took more than half an hour to start working).

While AWS Batch represents a valid solution for pure batch workloads, I was thinking
the conversion process something that would start as soon as the user uploads a new
file, and that runs in background, like many lengthy tasks that web applications
offload out of process to something else.

This could be an AWS Fargate Service, which again will be running our spleeter based
process within a Docker container. The container this time will run continuously based
on a Fargate Task definition, which will automatically scale the number of instances
when required.

The complexity of provisioning the required computing resources to properly run a 
container on Fargate is not trivial.
That would certainly be another job for Terraform, but I got caugth by this great
live demo, of building the same type of application, using AWS Cloud Development Kit.

Think about it as a typed *Python* wapper on top of CloudFormation (in reality the Python support is achieved through a language level binding over the Typescript implementation), which is able to generate CloudFormation templates, resolving all references and reusing stacks as you would do with your code libraries.

### CDK based solution

#### The worker stack

A `QueueProcessingFargateService` could be used to implement a separator worker, which will get items
(an S3 url to a file) from a job queue.

Files will be read from an input S3 bucket and output written back to an output bucket.
Worker pool will automatically scale when needed.

#### The HTTP API

As a frontend, we need an HTTP API, to perform at least the following operations:

  - push a new job and return an id
  - get the status of a job, given it's id

In my mind, this is more a job for a lambda function (or a group of lambda functions), especially in 2020, but in
order to get a first working version sooner, I would stick to a daemon style container, exposed to the internet
 using an Application load balancer, which happen to be directly supported by the high level patterns library 
 included in CDK.

An `ApplicationLoadBalancedFargateService` stack would do the trick then.

##### Installing CDK

CDK command line is needed during local development and later will be needed on CircleCI.
I installed the CDK command line (which is based on NodeJS) using:

  brew install aws-cdk

To test it worked, I run:

  cdk --version
  1.32.2 (build e19e206)

##### AWS credentials

I will use the same credentials from my personal AWS account to use CDK.
I created a new user `aws-cdk` within my personal account and gave him the following permissions:

  - SystemAdministrator
  - AWSCloudFormationFullAccess

As a personal memo, I will use the new `personal-cdk` profile (in `~/.aws/credentials`).

It's *important* to export the following environment variable:

  export AWS_PROFILE=personal-cdk

##### Creating the CDK project

I had to create a new empty directory to successfully run:

  cdk init app --language python

which conveniently created a blank project which includes a local virtualenv.
To activate the virtual environment for the project, issue the following command:

  source .env/bin/activate

and then, to install the required dependencies:

  pip install -r requirements.txt


##### Bootstraping the CDK toolkit

CDK toolkit need some resources to run its lifecycle commands.
An S3 bucket and a CloudFormation stack will be created performing the following
command:

  cdk bootstrap

Ideally this command should be run only once.
This is how it went for me:

  (.env)  AWS: personal-cdk  domenico@domecbook  ~/dev/experiments/karaokeme-cdk   master ●  cdk bootstrap
                <aws:personal-cdk>
  ⏳  Bootstrapping environment aws://521097367553/eu-west-1...
  CDKToolkit: creating CloudFormation changeset...
  0/3 | 12:28:08 PM | CREATE_IN_PROGRESS   | AWS::S3::Bucket       | StagingBucket
  0/3 | 12:28:09 PM | CREATE_IN_PROGRESS   | AWS::S3::Bucket       | StagingBucket Resource creation Initiated
  1/3 | 12:28:31 PM | CREATE_COMPLETE      | AWS::S3::Bucket       | StagingBucket
  1/3 | 12:28:33 PM | CREATE_IN_PROGRESS   | AWS::S3::BucketPolicy | StagingBucketPolicy
  1/3 | 12:28:34 PM | CREATE_IN_PROGRESS   | AWS::S3::BucketPolicy | StagingBucketPolicy Resource creation Initiated
  2/3 | 12:28:34 PM | CREATE_COMPLETE      | AWS::S3::BucketPolicy | StagingBucketPolicy
  3/3 | 12:28:35 PM | CREATE_COMPLETE      | AWS::CloudFormation::Stack | CDKToolkit

After that I've configured my Visual Studio Code with the AWS Toolkit
extension, which is really useful and easy to use.

#### Coding the infrastructure with CDK

I've started with refactoring the application code as suggested
in the demo video.

There will be shared resorces, and possibly references between the
 stacks. For this reason the Application object can hold a reference
 to the other component stacks.

After some coding (pretty east to be honest), it was time to deploy, which I did with the following command:

  cdk deploy '*'

Using two simple placeholder containers and after a couple of iterations 
where I had to destroy the stacks (some missing permissions for the AWS
 user), it worked as expected.

A very nice feeling.

During the next iteration I will need to perform the "actual" work that my
projects need to do.

The real API container must be able to enqueue a new job, both writing to
a DynamoDB table the entry and pushing it to the processing queue monitored
by the worker pool.

The worker, is also able to update the DynamoDB table to reflect the job 
status in the long-term storage.

#### Refining the architecture

The *HTTP API* will expose the following operations:


POST /jobs -> {job_id: 4j6h5k6e5h6jke5hjhj5, status: "uploading"}

it will perform the following things:

- generate a unique ID and a unique `s3_key`
- return a pre-signed URL to upload a file to `s3_key`
- add a row to the DynamoDB table including the `job_id`, the `s3_key` and the status `uploading`

At this point it's possible for the caller to upload a file using the pre-signed URL
returned by the first request.

Once the upload has completed client will call

POST /jobs/:id/process

This will trigger the processing, performing the following:
  - read the object from the DynamoDB table
  - add an object to the processing queue, including the `s3_key` and the `job_id`
  - update the DynamoDB row with the status `processing`

GET /jobs/:id
will return the job status or 404

GET /jobs
will return the full list of the jobs

I could quickly implement it with Flask and boto3. 
Of course I've omitted a number of things for a production ready
setup, like running flask on a WSGI container and didn't write 
any tests yet (which I'm confident can be arranged with pytest and moto/localstack).

The *worker cluster* will need to slightly adjust the one 
I wrote for the terraform version.
Some remarks:
- I had to add a polling mechanism to peek for messages from 
the associated processing queue

### CDK Python instructions

This is a blank project for Python development with CDK.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the .env
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .env
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .env/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .env\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!
