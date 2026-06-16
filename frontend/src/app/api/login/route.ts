import { NextRequest, NextResponse } from "next/server";

function getUpstreamSetCookies(headers: Headers): string[] {
  return headers.getSetCookie?.() ?? [headers.get("set-cookie")].filter(Boolean);
}

function readCookieValue(setCookie: string, name: string): string | undefined {
  const [cookiePair] = setCookie.split(";", 1);
  if (!cookiePair) {
    return undefined;
  }
  const [cookieName, ...valueParts] = cookiePair.split("=");
  if (cookieName?.trim() !== name) {
    return undefined;
  }
  const value = valueParts.join("=");
  return value ? decodeURIComponent(value) : undefined;
}

async function readUpstreamError(res: Response) {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json();
  }

  const text = await res.text();
  return { detail: text || "Login failed" };
}

function isSecureRequest(request: NextRequest): boolean {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedProto) {
    return forwardedProto.split(",")[0]?.trim().toLowerCase() === "https";
  }
  return request.nextUrl.protocol === "https:";
}

export async function POST(request: NextRequest) {
  const body = await request.json();
  const gatewayUrl =
    process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8001";
  const secureCookie = isSecureRequest(request);

  const res = await fetch(`${gatewayUrl}/api/admin/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const data = await readUpstreamError(res);
    return NextResponse.json(data, { status: res.status });
  }

  const data = await res.json();
  const response = NextResponse.json(data);

  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    secure: secureCookie,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 12,
  });

  response.cookies.set("refresh_token", data.refresh_token, {
    httpOnly: true,
    secure: secureCookie,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });

  for (const setCookie of getUpstreamSetCookies(res.headers)) {
    const csrfToken = readCookieValue(setCookie, "csrf_token");
    if (!csrfToken) {
      continue;
    }
    response.cookies.set("csrf_token", csrfToken, {
      httpOnly: false,
      secure: secureCookie,
      sameSite: "strict",
      path: "/",
    });
    break;
  }

  return response;
}
