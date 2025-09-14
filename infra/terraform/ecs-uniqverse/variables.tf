variable "region" { type = string }
variable "name_prefix" { type = string, default = "uniqverse" }

variable "cluster_arn" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }

variable "image" { type = string }
variable "desired_count" { type = number, default = 1 }
variable "service_port" { type = number, default = 8000 }
variable "health_check_path" { type = string, default = "/health" }

variable "task_cpu" { type = number, default = 512 }
variable "task_memory" { type = number, default = 1024 }
variable "container_env" {
  type    = map(string)
  default = {}
}

variable "create_task_sg" { type = bool, default = true }
variable "alb_security_group_id" { type = string, default = null }

variable "listener_arn" { type = string, default = null }
variable "create_listener_rule" { type = bool, default = false }
variable "listener_rule_priority" { type = number, default = 100 }
variable "listener_rule_paths" { type = list(string), default = ["/"] }
