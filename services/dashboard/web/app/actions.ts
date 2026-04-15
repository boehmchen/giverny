"use server";

import { revalidatePath } from "next/cache";
import { post } from "./lib/api";

export async function projectAction(formData: FormData) {
  const name = String(formData.get("name"));
  const action = String(formData.get("action"));
  await post(`/api/projects/${encodeURIComponent(name)}/${action}`);
  revalidatePath("/");
}

export async function serviceAction(formData: FormData) {
  const name = String(formData.get("name"));
  const service = String(formData.get("service"));
  const action = String(formData.get("action"));
  await post(
    `/api/projects/${encodeURIComponent(name)}/services/${encodeURIComponent(service)}/${action}`,
  );
  revalidatePath("/");
}

export async function linkRepo(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  const repo = String(formData.get("repo") ?? "").trim();
  const branch = String(formData.get("branch") ?? "main").trim();
  await post("/api/link", { name, repo, branch });
  revalidatePath("/");
}

export async function unlinkRepo(formData: FormData) {
  const name = String(formData.get("name"));
  await post(`/api/projects/${encodeURIComponent(name)}/unlink`);
  revalidatePath("/");
}

export async function setIdleTimeout(formData: FormData) {
  const name = String(formData.get("name"));
  const minutes = Number(formData.get("minutes"));
  await post(`/api/projects/${encodeURIComponent(name)}/idle-timeout`, {
    minutes,
  });
  revalidatePath("/");
}
