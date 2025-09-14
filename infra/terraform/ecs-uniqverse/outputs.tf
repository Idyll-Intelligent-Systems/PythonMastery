output "target_group_arn" {
  value = aws_lb_target_group.svc.arn
}

output "service_arn" {
  value = aws_ecs_service.svc.id
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.svc.arn
}
