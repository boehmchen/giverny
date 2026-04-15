"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { getJson, post } from "./lib/api";

const FLASH_COOKIE = "giverny_flash";

async function run(label: string, fn: () => Promise<void>) {
  const jar = await cookies();
  try {
    await fn();
    jar.delete(FLASH_COOKIE);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    jar.set(FLASH_COOKIE, JSON.stringify({ label, msg }), {
      maxAge: 30,
      path: "/",
      httpOnly: true,
      sameSite: "lax",
    });
  }
  revalidatePath("/");
}

export async function projectAction(formData: FormData) {
  const name = String(formData.get("name"));
  const action = String(formData.get("action"));
  await run(`${action} ${name}`, () =>
    post(`/api/projects/${encodeURIComponent(name)}/${action}`),
  );
}

export async function serviceAction(formData: FormData) {
  const name = String(formData.get("name"));
  const service = String(formData.get("service"));
  const action = String(formData.get("action"));
  await run(`${action} ${name}/${service}`, () =>
    post(
      `/api/projects/${encodeURIComponent(name)}/services/${encodeURIComponent(service)}/${action}`,
    ),
  );
}

export async function linkRepo(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  const repo = String(formData.get("repo") ?? "").trim();
  const branch = String(formData.get("branch") ?? "main").trim();
  await run(`link ${name}`, () =>
    post("/api/link", { name, repo, branch }),
  );
}

export async function unlinkRepo(formData: FormData) {
  const name = String(formData.get("name"));
  await run(`unlink ${name}`, () =>
    post(`/api/projects/${encodeURIComponent(name)}/unlink`),
  );
}

export async function setIdleTimeout(formData: FormData) {
  const name = String(formData.get("name"));
  const minutes = Number(formData.get("minutes"));
  await run(`idle-timeout ${name}`, () =>
    post(`/api/projects/${encodeURIComponent(name)}/idle-timeout`, { minutes }),
  );
}

export async function rebuildProject(formData: FormData) {
  const name = String(formData.get("name"));
  await run(`rebuild ${name}`, () =>
    post(`/api/projects/${encodeURIComponent(name)}/rebuild`),
  );
}

export async function dismissFlash() {
  (await cookies()).delete(FLASH_COOKIE);
  revalidatePath("/");
}

export async function fetchBuildLog(name: string): Promise<string[]> {
  const res = await getJson<{ lines: string[] }>(
    `/api/projects/${encodeURIComponent(name)}/build-log`,
  );
  return res.lines;
}

export async function fetchServiceLog(
  name: string,
  service: string,
): Promise<string[]> {
  const res = await getJson<{ lines: string[] }>(
    `/api/projects/${encodeURIComponent(name)}/services/${encodeURIComponent(service)}/log`,
  );
  return res.lines;
}
