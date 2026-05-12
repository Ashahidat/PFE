const TOKEN_KEY = "access_token";
const LAST_DATASET_KEY = "last_dataset_id";
const LAST_DAG_RUN_KEY = "last_dag_run_id";
const USER_ROLE_KEY = "user_role";
const USER_DEPT_KEY = "user_department";
const USERNAME_KEY = "user_username";
const EMPLOYEE_ID_KEY = "user_employee_id";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_ROLE_KEY);
  localStorage.removeItem(USER_DEPT_KEY);
  localStorage.removeItem(USERNAME_KEY);
  localStorage.removeItem(EMPLOYEE_ID_KEY);
}

export function getLastDatasetId(): string | null {
  return localStorage.getItem(LAST_DATASET_KEY);
}

export function setLastDatasetId(id: string): void {
  localStorage.setItem(LAST_DATASET_KEY, id);
}

export function getLastDagRunId(): string | null {
  return localStorage.getItem(LAST_DAG_RUN_KEY);
}

export function setLastDagRunId(id: string): void {
  localStorage.setItem(LAST_DAG_RUN_KEY, id);
}

export function getUserRole(): string | null {
  return localStorage.getItem(USER_ROLE_KEY);
}

export function setUserRole(role: string): void {
  localStorage.setItem(USER_ROLE_KEY, role);
}

export function getUserDepartment(): string | null {
  return localStorage.getItem(USER_DEPT_KEY);
}

export function setUserDepartment(dept: string): void {
  localStorage.setItem(USER_DEPT_KEY, dept);
}

export function getUsername(): string | null {
  return localStorage.getItem(USERNAME_KEY);
}

export function setUsername(username: string): void {
  localStorage.setItem(USERNAME_KEY, username);
}

export function getEmployeeId(): string | null {
  return localStorage.getItem(EMPLOYEE_ID_KEY);
}

export function setEmployeeId(id: string): void {
  localStorage.setItem(EMPLOYEE_ID_KEY, id);
}
