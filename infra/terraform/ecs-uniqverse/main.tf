terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

locals {
  name = var.name_prefix
}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.name}"
  retention_in_days = 14
}

resource "aws_lb_target_group" "svc" {
  name        = "${local.name}-tg"
  port        = var.service_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    path                = var.health_check_path
    healthy_threshold   = 2
    unhealthy_threshold = 5
    interval            = 30
    timeout             = 5
    matcher             = "200-399"
  }
}

resource "aws_security_group" "task" {
  count       = var.create_task_sg ? 1 : 0
  name        = "${local.name}-task-sg"
  description = "Allow ALB to reach tasks on service port"
  vpc_id      = var.vpc_id

  ingress {
    description      = "ALB to tasks"
    from_port        = var.service_port
    to_port          = var.service_port
    protocol         = "tcp"
    security_groups  = var.alb_security_group_id != null ? [var.alb_security_group_id] : []
    cidr_blocks      = var.alb_security_group_id == null ? ["0.0.0.0/0"] : null
    ipv6_cidr_blocks = var.alb_security_group_id == null ? ["::/0"] : null
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-task-role"
  assume_role_policy = data.aws_iam_policy_document.task_assume.json
}

data "aws_iam_policy_document" "task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "task_exec" {
  role       = aws_iam_role.task.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_task_definition" "svc" {
  family                   = "${local.name}"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.task.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = local.name
      image     = var.image
      essential = true
      portMappings = [{
        containerPort = var.service_port
        hostPort      = var.service_port
        protocol      = "tcp"
      }]
      environment = [for k, v in var.container_env : { name = k, value = v }]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.ecs.name
          awslogs-region        = var.region
          awslogs-stream-prefix = local.name
        }
      }
      healthCheck = {
        command  = ["CMD-SHELL", "curl -f http://localhost:${var.service_port}${var.health_check_path} || exit 1"]
        interval = 30
        timeout  = 5
        retries  = 3
      }
    }
  ])
}

resource "aws_ecs_service" "svc" {
  name            = local.name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.svc.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    assign_public_ip = false
    security_groups = var.create_task_sg ? [aws_security_group.task[0].id] : []
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.svc.arn
    container_name   = local.name
    container_port   = var.service_port
  }

  lifecycle {
    ignore_changes = [desired_count]
  }
}

resource "aws_lb_listener_rule" "svc" {
  count        = var.create_listener_rule && var.listener_arn != null ? 1 : 0
  listener_arn = var.listener_arn
  priority     = var.listener_rule_priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.svc.arn
  }

  condition {
    path_pattern {
      values = var.listener_rule_paths
    }
  }
}
