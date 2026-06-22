import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Socket } from 'node:net'
import type { Plugin, PreviewServer, ProxyOptions, ViteDevServer } from 'vite'

const socketErrorHandled = Symbol('adminProxySocketErrorHandled')
const processErrorHandled = Symbol.for('deerflow.admin.processSocketErrorHandled')
const resetLikeErrorCodes = new Set(['ECONNRESET', 'EPIPE', 'ECONNREFUSED', 'ETIMEDOUT'])

type SocketWithErrorHandlerFlag = Socket & {
  [socketErrorHandled]?: true
}

type ProcessWithErrorHandlerFlag = NodeJS.Process & {
  [processErrorHandled]?: true
}

function getErrorCode(error: unknown): string | undefined {
  if (typeof error !== 'object' || error === null) {
    return undefined
  }
  const code = Reflect.get(error, 'code')
  return typeof code === 'string' ? code : undefined
}

function isResetLikeNetworkError(error: unknown): boolean {
  const code = getErrorCode(error)
  return code ? resetLikeErrorCodes.has(code) : false
}

function attachSocketErrorHandler(socket: Socket | null | undefined): void {
  if (!socket) {
    return
  }
  const guardedSocket = socket as SocketWithErrorHandlerFlag
  if (guardedSocket[socketErrorHandled]) {
    return
  }
  guardedSocket[socketErrorHandled] = true
  guardedSocket.on('error', (error) => {
    if (isResetLikeNetworkError(error)) {
      return
    }
    console.error('[admin:vite-proxy] socket error', error)
  })
}

function installProcessSocketErrorGuard(): void {
  const guardedProcess = process as ProcessWithErrorHandlerFlag
  if (guardedProcess[processErrorHandled]) {
    return
  }
  guardedProcess[processErrorHandled] = true
  process.on('uncaughtException', (error) => {
    if (isResetLikeNetworkError(error)) {
      console.warn('[admin:vite] ignored transient socket error', getErrorCode(error))
      return
    }
    throw error
  })
}

function attachHttpServerSocketErrorHandlers(server: ViteDevServer | PreviewServer): void {
  installProcessSocketErrorGuard()
  const httpServer = server.httpServer
  if (!httpServer) {
    return
  }
  httpServer.on('connection', (socket) => {
    attachSocketErrorHandler(socket)
  })
  httpServer.on('clientError', (error, socket) => {
    if (!isResetLikeNetworkError(error)) {
      console.error('[admin:vite] client error', error)
    }
    socket.destroy()
  })
}

function adminSocketErrorGuard(): Plugin {
  return {
    name: 'admin-socket-error-guard',
    configureServer: attachHttpServerSocketErrorHandlers,
    configurePreviewServer: attachHttpServerSocketErrorHandlers,
  }
}

function sendProxyFailure(res: unknown): void {
  if (typeof res !== 'object' || res === null) {
    return
  }
  const response = res as Partial<ServerResponse<IncomingMessage>>
  if (
    response.headersSent ||
    typeof response.writeHead !== 'function' ||
    typeof response.end !== 'function'
  ) {
    return
  }
  response.writeHead(502, { 'Content-Type': 'application/json; charset=utf-8' })
  response.end(JSON.stringify({ detail: 'Admin API gateway is unavailable' }))
}

const configureApiProxy: NonNullable<ProxyOptions['configure']> = (proxy) => {
  proxy.on('proxyReq', (proxyReq, req) => {
    attachSocketErrorHandler(proxyReq.socket)
    attachSocketErrorHandler(req.socket)
  })
  proxy.on('proxyRes', (proxyRes, req) => {
    attachSocketErrorHandler(proxyRes.socket)
    attachSocketErrorHandler(req.socket)
  })
  proxy.on('error', (error, _req, res) => {
    if (!isResetLikeNetworkError(error)) {
      console.error('[admin:vite-proxy] proxy error', error)
    }
    sendProxyFailure(res)
  })
}

const apiProxy: Record<string, ProxyOptions> = {
  '/api': {
    target: 'http://localhost:8001',
    changeOrigin: false,
    configure: configureApiProxy,
  },
}

export default defineConfig({
  base: '/admin/',
  plugins: [
    adminSocketErrorGuard(),
    react(),
    tailwindcss(),
  ],
  server: {
    port: 3002,
    proxy: apiProxy,
  },
  preview: {
    port: 3002,
    proxy: apiProxy,
  },
})
