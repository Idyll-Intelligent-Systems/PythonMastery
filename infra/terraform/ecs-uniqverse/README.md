ECS (Fargate) — UniQVerse Service behind existing ALB

This Terraform stack creates:

- An ECS task definition (Fargate) for the UniQVerse container image
- An ECS service that registers tasks with a new Target Group
- A new ALB Target Group (HTTP, target_type=ip) on the UniQVerse serving port
- Optional listener rule to attach the Target Group to an existing ALB listener
- CloudWatch Log Group for ECS logs
- Optional Security Group for tasks that allows ingress from the ALB SG on the service port

Assumptions:
- You already have: VPC, subnets, ECS cluster, ALB, and an ALB listener
- ECR image exists (e.g., 123456789012.dkr.ecr.eu-north-1.amazonaws.com/veze/uniqverse:latest)

Quick start

1) Set variables in a tfvars file (example `dev.tfvars`):

```
region                   = "eu-north-1"
cluster_arn              = "arn:aws:ecs:eu-north-1:123456789012:cluster/veze-cluster"
vpc_id                   = "vpc-0123456789abcdef0"
private_subnet_ids       = ["subnet-aaa", "subnet-bbb"]
alb_security_group_id    = "sg-alb123456"
listener_arn             = "arn:aws:elasticloadbalancing:eu-north-1:123456789012:listener/app/veze-alb/abc/def"
image                    = "123456789012.dkr.ecr.eu-north-1.amazonaws.com/veze/uniqverse:latest"
desired_count            = 2
service_port             = 8000
health_check_path        = "/health"
task_cpu                 = 512
task_memory              = 1024
container_env = {
  "ENV" = "dev"
}
create_listener_rule     = true
listener_rule_priority   = 110
listener_rule_paths      = ["/"]
name_prefix              = "uniqverse"
```

2) Init and apply:

```
terraform init
terraform apply -var-file=dev.tfvars
```

Key variables

- `image` (required): Full image reference, e.g., ECR image for veze/uniqverse
- `cluster_arn` (required): Existing ECS cluster ARN
- `vpc_id`, `private_subnet_ids` (required): For awsvpc networking
- `service_port` (default 8000): Container and TG port
- `alb_security_group_id` (required if `create_task_sg=true`): Allows ingress to tasks from ALB
- `listener_arn`, `create_listener_rule` (optional): Attach TG to an existing listener with a rule

Outputs

- `target_group_arn`, `service_arn`, `task_definition_arn`
