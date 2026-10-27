variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "environment" {
  type    = string
  default = "demo"
}
variable "owner" {
  type = string
  validation {
    condition     = length(trimspace(var.owner)) > 0
    error_message = "Record a resource owner."
  }
}
variable "teardown_date" {
  type = string
  validation {
    condition     = can(regex("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", var.teardown_date))
    error_message = "Record the planned teardown date as YYYY-MM-DD."
  }
}
variable "ubuntu_ami_id" {
  type = string
  validation {
    condition     = can(regex("^ami-[0-9a-f]+$", var.ubuntu_ami_id))
    error_message = "Supply a reviewed Ubuntu 24.04 x86_64 AMI for the region."
  }
}
variable "availability_zone" { type = string }
variable "ec2_key_name" { type = string }
variable "admin_ssh_cidrs" {
  type = list(string)
  validation {
    condition = length(var.admin_ssh_cidrs) > 0 && alltrue([
      for c in var.admin_ssh_cidrs : can(cidrnetmask(c)) && try(tonumber(split("/", c)[1]) > 0, false)
    ])
    error_message = "Supply restricted IPv4 CIDRs; /0 is forbidden."
  }
}
variable "instance_type" {
  type    = string
  default = "c7i-flex.large"
}
variable "k3s_version" {
  type    = string
  default = "v1.37.1+k3s1"
  validation {
    condition     = can(regex("^v[0-9]+\\.[0-9]+\\.[0-9]+\\+k3s[0-9]+$", var.k3s_version))
    error_message = "Use an explicit K3s version."
  }
}
variable "k3s_binary_sha256" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.k3s_binary_sha256))
    error_message = "Supply the reviewed official amd64 checksum for the K3s release."
  }
}
