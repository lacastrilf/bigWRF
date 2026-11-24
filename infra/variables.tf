variable "region" {
  type    = string
  default = "us-east-1"
}
variable "lab_role_name" {
  type    = string
  default = "LabRole"
}
variable "instance_profile_name" {
  description = "Perfil de instancia para EC2 y nodos EMR"
  type        = string
  default     = "LabInstanceProfile"
}
variable "emr_service_role" {
  description = "Rol de servicio de EMR (LabRole no tiene permisos EC2 suficientes para EMR)"
  type        = string
  default     = "EMR_DefaultRole"
}
variable "emr_instance_profile" {
  description = "Perfil de instancia de los nodos EMR"
  type        = string
  default     = "EMR_EC2_DefaultRole"
}
variable "key_name" {
  type    = string
  default = "vockey"
}
variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}
variable "my_ip_cidr" {
  description = "Tu IP publica en /32 para SSH (ej. 190.1.2.3/32)"
  type        = string
}
variable "ec2_disk_gb" {
  description = "Disco de la EC2 fuente. Debe caber los wrfout originales (max 100 en el lab)"
  type        = number
  default     = 100
}
variable "db_name" {
  type    = string
  default = "derecho"
}
variable "db_user" {
  type    = string
  default = "admin"
}
variable "enable_nat" {
  type    = bool
  default = true
}
variable "enable_ec2" {
  type    = bool
  default = true
}
variable "enable_rds" {
  type    = bool
  default = true
}
variable "enable_emr" {
  description = "EMR cuesta ~USD 0.72/h. Ponlo en false para no crearlo"
  type        = bool
  default     = true
}
variable "emr_idle_timeout_s" {
  description = "Terminacion automatica por inactividad (segundos)"
  type        = number
  default     = 3600
}
variable "emr_instance_type" {
  type    = string
  default = "m5.xlarge"
}
