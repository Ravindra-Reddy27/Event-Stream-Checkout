# iac/database.tf

# 1. Random Password for Database
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# 2. Store Password in AWS Secrets Manager (Security Best Practice)
resource "aws_secretsmanager_secret" "db_credentials" {
  name = "${var.project_name}-db-credentials-${random_string.suffix.result}"
}

resource "aws_secretsmanager_secret_version" "db_credentials_val" {
  secret_id     = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "admin"
    password = random_password.db_password.result
    engine   = "mysql"
    host     = aws_db_instance.default.address
    port     = 3306
    dbname   = "ecommerce"
  })
}

resource "random_string" "suffix" {
  length  = 4
  special = false
  upper   = false
}

# 3. Security Group: Allow Lambda to connect to RDS
resource "aws_security_group" "rds_sg" {
  name        = "${var.project_name}-rds-sg"
  description = "Allow MySQL access"

  ingress {
    from_port   = 3306
    to_port     = 3306
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # For simplicity in this tutorial. In prod, restrict to VPC.
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 4. The MySQL RDS Instance
resource "aws_db_instance" "default" {
  allocated_storage      = 20
  storage_type           = "gp2"
  engine                 = "mysql"
  engine_version         = "8.0"
  instance_class         = "db.t3.micro" # Free tier eligible
  identifier             = "${var.project_name}-db"
  username               = "admin"
  password               = random_password.db_password.result
  parameter_group_name   = "default.mysql8.0"
  skip_final_snapshot    = true
  publicly_accessible    = true # Set to true so you can connect from your local machine to initialize tables
  vpc_security_group_ids = [aws_security_group.rds_sg.id]
  db_name                = "ecommerce"
}