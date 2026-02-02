const BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export function getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("token");
}

export function setToken(token: string) {
    localStorage.setItem("token", token);
}

export function clearToken() {
    localStorage.removeItem("token");
}

type HttpMethod = "GET" | "POST" | "PUT" | "DELETE";

export async function api<T>(
    path: string,
    method: HttpMethod = "GET",
    body?: any
): Promise<T> {
    const token = getToken();

    const res = await fetch(`${BASE}${path}`, {
        method,
        headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
    });

    // Try to parse JSON error bodies
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;

    if (!res.ok) {
        const msg = data?.detail || data?.message || `Request failed (${res.status})`;
        throw new Error(msg);
    }

    return data as T;
}
