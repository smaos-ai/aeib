output "phase_37_summary" {
  value = {
    defense = {
      instance_id = aws_instance.defense_primary.id
      private_ip  = aws_instance.defense_primary.private_ip
      vpc_id      = aws_vpc.defense_vpc.id
      vertical    = "Defense"
      sla_target  = "99.99%"
      arr_commitment_cents = var.arr_commitment_defense
    }
    healthcare = {
      instance_id = aws_instance.healthcare_primary.id
      private_ip  = aws_instance.healthcare_primary.private_ip
      vpc_id      = aws_vpc.healthcare_vpc.id
      vertical    = "Healthcare"
      sla_target  = "99.99%"
      arr_commitment_cents = var.arr_commitment_healthcare
    }
    finance = {
      instance_id = aws_instance.finance_primary.id
      private_ip  = aws_instance.finance_primary.private_ip
      vpc_id      = aws_vpc.finance_vpc.id
      vertical    = "Finance"
      sla_target  = "99.99%"
      arr_commitment_cents = var.arr_commitment_finance
      settlements_table = aws_dynamodb_table.finance_settlements.id
    }
    total_arr_cents = var.arr_commitment_defense + var.arr_commitment_healthcare + var.arr_commitment_finance
    pilot_duration_days = var.pilot_duration_days
  }
  description = "Phase 37 GTM summary: 3-vertical deployment with €5M ARR target"
}
