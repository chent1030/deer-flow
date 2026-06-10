export enum UserRole {
  SUPER_ADMIN = "super_admin",
  DEPT_ADMIN = "dept_admin",
  USER = "user",
}

export enum UserStatus {
  ACTIVE = "active",
  DISABLED = "disabled",
}

export enum SkillVisibility {
  COMPANY = "company",
  DEPARTMENT = "department",
  SPECIFIC_USERS = "specific_users",
  PRIVATE = "private",
}

export enum SkillStatus {
  PENDING_REVIEW = "pending_review",
  APPROVED = "approved",
  REJECTED = "rejected",
  WITHDRAWN = "withdrawn",
}

export interface User {
  id: string;
  username: string;
  display_name: string;
  email: string;
  role: UserRole;
  department_id: string | null;
  status: UserStatus;
  created_at: string | null;
}

export interface Department {
  id: string;
  name: string;
  parent_id: string | null;
  created_at: string | null;
  children: Department[];
  member_count: number;
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  version: string;
  author_id: string;
  department_id: string | null;
  visibility: SkillVisibility;
  status: SkillStatus;
  file_size: number;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
  created_at: string | null;
  author_name: string | null;
  department_name: string | null;
  visible_user_ids: string[];
  visible_department_ids: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
