import { NextRequest, NextResponse } from "next/server";

const BACKEND_BASE = process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

function buildTarget(path: string[] | undefined, request: NextRequest): string {
  const routePath = (path || []).join("/");
  const search = request.nextUrl.search || "";
  return `${BACKEND_BASE.replace(/\/$/, "")}/${routePath}${search}`;
}

async function forward(request: NextRequest, context: { params: { path?: string[] } }) {
  const target = buildTarget(context.params.path, request);
  const method = request.method;
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");

  const init: RequestInit = { method, headers, redirect: "manual" };
  if (!["GET", "HEAD"].includes(method)) {
    init.body = await request.arrayBuffer();
  }

  const upstream = await fetch(target, init);
  const responseHeaders = new Headers(upstream.headers);
  responseHeaders.delete("content-encoding");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders
  });
}

export async function GET(request: NextRequest, context: { params: { path?: string[] } }) { return forward(request, context); }
export async function POST(request: NextRequest, context: { params: { path?: string[] } }) { return forward(request, context); }
export async function PUT(request: NextRequest, context: { params: { path?: string[] } }) { return forward(request, context); }
export async function PATCH(request: NextRequest, context: { params: { path?: string[] } }) { return forward(request, context); }
export async function DELETE(request: NextRequest, context: { params: { path?: string[] } }) { return forward(request, context); }
export async function OPTIONS(request: NextRequest, context: { params: { path?: string[] } }) { return forward(request, context); }