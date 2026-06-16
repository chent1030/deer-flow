import { NextRequest, NextResponse } from "next/server";

async function readUpstreamError(res: Response) {
  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json();
  }

  const text = await res.text();
  return { detail: text || "修改密码失败" };
}

export async function PUT(request: NextRequest) {
  const token = request.cookies.get("access_token")?.value;
  if (!token) {
    return NextResponse.json(
      { detail: "请先登录" },
      { status: 401 },
    );
  }
  const csrfToken =
    request.headers.get("x-csrf-token") ??
    request.cookies.get("csrf_token")?.value;

  const body = (await request.json()) as {
    current_password?: string;
    new_password?: string;
  };

  const gatewayUrl =
    process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8001";
  const res = await fetch(`${gatewayUrl}/api/admin/auth/me/password`, {
    method: "PUT",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(csrfToken
        ? {
            Cookie: `csrf_token=${encodeURIComponent(csrfToken)}`,
            "X-CSRF-Token": csrfToken,
          }
        : {}),
    },
    body: JSON.stringify({
      old_password: body.current_password,
      new_password: body.new_password,
    }),
  });

  if (!res.ok) {
    const data = await readUpstreamError(res);
    return NextResponse.json(data, { status: res.status });
  }

  const data = await res.json();
  return NextResponse.json(data);
}
