<!-- mcp-name: io.github.GermaniU/ga4-seo-mcp -->

[English](https://github.com/GermaniU/ga4-seo-mcp/blob/main/README.md) · **Español**

# ga4-seo-mcp — la medición de un sitio, de punta a punta, para agentes de IA

> **Deja la medición de un sitio lista de punta a punta: GA4 + Search Console + PageSpeed, con escritura opcional y protegida.**
> Servidor open source de [Model Context Protocol](https://modelcontextprotocol.io) para Google Analytics 4 y Search Console. La mayoría de los servidores MCP para Google *leen* tus datos; este además **los configura**: propiedad, data stream, key events, custom dimensions, verificación DNS en Search Console, sitemap y una línea base de PageSpeed. Es de solo lectura hasta que tú digas lo contrario.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/GermaniU/ga4-seo-mcp/blob/main/LICENSE)
[![MCP](https://img.shields.io/badge/MCP-stdio_%7C_Streamable_HTTP-green)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://github.com/GermaniU/ga4-seo-mcp/blob/main/pyproject.toml)
[![CI](https://github.com/GermaniU/ga4-seo-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/GermaniU/ga4-seo-mcp/actions/workflows/ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/GermaniU/ga4-seo-mcp/blob/main/CONTRIBUTING.md)

<p align="center">
  <img src="https://raw.githubusercontent.com/GermaniU/ga4-seo-mcp/main/docs/assets/demo.gif" alt="Un agente audita un sitio público con PageSpeed y planea la configuración de GA4 + Search Console de un sitio nuevo" width="780">
</p>

<p align="center"><sub>Ejecución real: <code>psi_audit</code> sobre un sitio público y <code>bootstrap_site_measurement(apply=False)</code> planeando un sitio nuevo. El script del demo oculta el ID de la cuenta.</sub></p>

---

## 💡 ¿Por qué este?

Lanzar un sitio implica siempre las mismas tareas: crear la propiedad de GA4 y su web stream, marcar los key events, registrar las custom dimensions, agregar el dominio a Search Console, publicar un registro TXT en el DNS, verificarlo, enviar el sitemap y medir una línea base de PageSpeed. `ga4-seo-mcp` lo convierte en **un plan que tu agente te muestra y una sola confirmación**.

| | **ga4-seo-mcp** | [MCP oficial de GA4 de Google](https://github.com/googleanalytics/google-analytics-mcp) | [search-console-mcp](https://github.com/saurabhsharma2u/search-console-mcp) | [google-seo-mcp](https://github.com/Akxan/google-seo-mcp) |
|---|---|---|---|---|
| Reportes de GA4 (Data API) | ✅ | ✅ | ✅ | ✅ |
| Search Console | ✅ | — | ✅ (+ Bing) | ✅ |
| PageSpeed Insights / CrUX | ✅ | — | ✅ | ✅ |
| Crear propiedad GA4 + web stream | ✅ | — | — | — |
| Crear key events / custom dimensions | ✅ | — | — | ✅ |
| Verificación DNS en Search Console | ✅ | — | — | — |
| Plan → apply del sitio en una llamada (idempotente) | ✅ `bootstrap_site_measurement` | — | — | — |
| Solo lectura por defecto | ✅ las tools de escritura ni siquiera se registran | solo lectura | ver su documentación | ✅ modo solo lectura |
| Toolsets | ✅ | — | — | ✅ |
| Lenguaje | Python | Python | TypeScript | TypeScript |

<sub>Según el README de cada proyecto al 2026-10-19; "—" significa que no lo encontramos documentado. Se aceptan correcciones. Esos proyectos abarcan más que este (Bing, AdSense, WordPress, auditorías GEO…); este profundiza en **configurar** la medición.</sub>

Extras: keyword research opcional con **DataForSEO** (volúmenes exactos de long-tail) y **Google Ads Keyword Planner** (gratis, volúmenes por rangos), con valores por defecto para `es-MX` que puedes cambiar.

---

## 🤝 ¿Que te lo dejen configurado?

Este servidor lo construye y mantiene [Germani Uicab](https://serverstack.solutions/germani?utm_source=github&utm_medium=readme&utm_campaign=ga4-seo-mcp-es). Si prefieres no hacerlo tú mismo, [ServerStack Solutions](https://serverstack.solutions/germani?utm_source=github&utm_medium=readme&utm_campaign=ga4-seo-mcp-es) deja la medición de tu sitio lista: plan por escrito, propiedad GA4 y eventos clave configurados, verificación DNS y sitemap en Search Console, y línea base de PageSpeed, con QA antes de entregar.

---

## ⚡ Inicio rápido

**1. Instala [`uv`](https://docs.astral.sh/uv/)**: el cliente lanza el servidor con `uvx`, no hace falta instalar nada más.

**2. Inicia sesión con los permisos mínimos.** El CLI imprime el comando `gcloud` exacto para los toolsets que actives:

```bash
uvx ga4-seo-mcp auth-command --client-id-file=oauth-client.json
# gcloud auth application-default login --client-id-file=oauth-client.json --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/webmasters.readonly
```

Ejecuta el comando que imprime. Google bloquea los permisos de Analytics y Search Console en el cliente OAuth integrado de gcloud, así que necesitas uno propio (se configura una sola vez en unos minutos) **o** una cuenta de servicio. Las dos rutas están en [docs/AUTH.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/docs/AUTH.md).

**3. Revisa todo antes de conectar un cliente** (solo lectura, no cambia nada):

```bash
uvx ga4-seo-mcp doctor
```

**4. Agrégalo a tu cliente** (aquí Claude Code; los demás, [más abajo](#-conecta-tu-cliente)):

```bash
claude mcp add ga4-seo -- uvx ga4-seo-mcp
```

Pregunta: *"Lista mis propiedades de GA4 y muéstrame las sesiones de la última semana de la primera."*

> **Antes de la primera versión en PyPI**, ejecútalo desde GitHub: `uvx --from git+https://github.com/GermaniU/ga4-seo-mcp ga4-seo-mcp`.

---

## 🧰 Toolsets, permisos y tools

Activa solo lo que necesites con `--toolsets` (o `GA4SEO_TOOLSETS`). Por defecto: `admin,data,gsc,psi`. Solo se registran las tools de los toolsets activos, y los permisos OAuth se ajustan a ellos.

| Toolset | Qué cubre | Permisos (solo lectura) | Permisos extra con `--enable-writes` | Tools (lectura + escritura) |
|---|---|---|---|---|
| `admin` | GA4 Admin API: cuentas, propiedades, streams, key events, custom dimensions, vínculos con Ads, **`bootstrap_site_measurement`** | `analytics.readonly` | `analytics.edit` | 9 + 10 |
| `data` | GA4 Data API: reportes, tiempo real, top pages, eventos, fuentes de tráfico, portafolio | `analytics.readonly` | — | 8 + 0 |
| `gsc` | Search Console: queries, páginas, sitemaps, alta de dominio y verificación DNS | `webmasters.readonly` | `webmasters`, `siteverification` | 5 + 3 |
| `psi` | PageSpeed Insights: laboratorio de Lighthouse + datos de campo de CrUX | ninguno (se recomienda `PAGESPEED_API_KEY`) | — | 2 + 0 |
| `dataforseo` | Ideas de keywords y volúmenes exactos de DataForSEO (de pago) | ninguno (`DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`) | — | 2 + 0 |
| `ads` | Google Ads Keyword Planner (requiere `pip install 'ga4-seo-mcp[ads]'`) | `adwords` | — | 2 + 0 |

Conteos del registro real: **24** tools por defecto, **37** con `--enable-writes`, **8** con `--toolsets data` y **41** con todos los toolsets y escritura. La lista completa está en [docs/TOOLS.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/docs/TOOLS.md) (se genera desde el registro y la CI la verifica).

**Prompts:** `audit_ga4_setup`, `seo_360_audit`, `portfolio_performance_digest` y `launch_site_measurement` (el flujo guiado: plan → tu confirmación → apply → verificación DNS → sitemap → línea base de PageSpeed).

### `bootstrap_site_measurement`

- **`apply=False` (por defecto): un plan.** Es de solo lectura y siempre se registra. Detecta la propiedad y el web stream existentes por el dominio del sitio, los key events y custom dimensions ya declarados y la propiedad de dominio en Search Console, y lista lo que se crearía.
- **`apply=True`: ejecuta el plan.** Solo funciona si el servidor corre con `--enable-writes`; si no, falla antes de tocar nada. Es idempotente: salta lo que ya existe, así que puedes volver a ejecutarlo. Devuelve un reporte paso a paso con el measurement ID (`G-…`) y el token TXT para el DNS.
- La verificación DNS (`sc_verify_site_dns`) y el sitemap (`sc_submit_sitemap`) se quedan como pasos explícitos, porque antes tienes que publicar el registro TXT.

---

## 🔒 Modelo de seguridad

Los valores por defecto son seguros para una persona en su laptop. El detalle y el modelo de amenazas están en [SECURITY.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/SECURITY.md).

- **Solo lectura por defecto.** Sin `--enable-writes` (o `GA4SEO_ENABLE_WRITES=1`), las tools que crean, actualizan, borran, envían o verifican **no se registran**: el modelo no puede llamar lo que no existe.
- **Anotaciones MCP** en cada tool: `readOnlyHint` en las de lectura, `destructiveHint` en las que borran o sobrescriben, `idempotentHint` donde repetir no hace daño y `openWorldHint` en todas.
- **Permisos mínimos**: cada cliente de Google pide solo el permiso de la llamada que hace, y `auth-command` pide solo los de tus toolsets.
- **Transporte HTTP** (`--transport streamable-http`): escucha en `127.0.0.1`, con protección contra DNS rebinding activa, CORS apagado salvo que definas `MCP_CORS_ORIGINS` y bearer token opcional `MCP_AUTH_TOKEN` (responde 401 sin él). Si escuchas en `0.0.0.0` sin token, imprime una advertencia.
- **Secretos** (DataForSEO, developer token de Ads, key de PageSpeed): salen solo de variables de entorno o de un archivo con `chmod 600`, y nunca se registran en logs ni se devuelven en errores.

---

## ⚙️ Configuración

| Variable | Por defecto | Descripción |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Archivo de llave de una cuenta de servicio. Sin definir = Application Default Credentials de `gcloud`. |
| `GA4SEO_TOOLSETS` | `admin,data,gsc,psi` | Igual que `--toolsets`. |
| `GA4SEO_ENABLE_WRITES` | `0` | `1` = igual que `--enable-writes`. |
| `PAGESPEED_API_KEY` | — | Recomendada: la cuota anónima de PageSpeed es compartida y suele estar agotada (429). |
| `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD` | — | Toolset `dataforseo`. |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | — | Toolset `ads`, o `~/.config/ga4-seo-mcp/dev-token` con `chmod 600`. |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | — | Solo si operas a través de una cuenta de administrador (MCC). |
| `MCP_TRANSPORT` | `stdio` | `stdio`, `streamable-http` o `sse`. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | Dirección y puerto HTTP. Una dirección concreta que no sea loopback se agrega a los `Host` permitidos; `0.0.0.0` no, así que para clientes en la LAN define `MCP_ALLOWED_HOSTS`. |
| `MCP_AUTH_TOKEN` | — | Exige `Authorization: Bearer <token>` en cada petición HTTP. |
| `MCP_CORS_ORIGINS` | — | Orígenes exactos, separados por coma, para un cliente en el navegador. Nunca `*`. |
| `MCP_ALLOWED_HOSTS` | — | Hosts o IPs que usan tus clientes, separados por coma (p. ej. `192.168.1.10`). Hace falta al escuchar en `0.0.0.0` y conectar por la LAN; el resto recibe `421`. |

---

## 🔌 Conecta tu cliente

Todos los clientes lanzan el servidor por stdio. Agrega `--enable-writes` a `args` solo en la sesión en la que de verdad vas a configurar un sitio.

**Claude Code**

```bash
claude mcp add ga4-seo -- uvx ga4-seo-mcp
```

**Claude Desktop** (`claude_desktop_config.json`) y **Cursor** (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "ga4-seo": {
      "command": "uvx",
      "args": ["ga4-seo-mcp"],
      "env": { "PAGESPEED_API_KEY": "tu-key" }
    }
  }
}
```

**VS Code** (`.vscode/mcp.json`)

```json
{
  "servers": {
    "ga4-seo": { "type": "stdio", "command": "uvx", "args": ["ga4-seo-mcp"] }
  }
}
```

**Docker** (stdio). Monta tu archivo de credenciales en solo lectura (el de ADC de `gcloud` o la llave de una cuenta de servicio) y corre el contenedor con tu propio usuario para que pueda leer un archivo `0600`:

```bash
docker run -i --rm --user "$(id -u):$(id -g)" \
  -v ~/.config/gcloud/application_default_credentials.json:/creds/credentials.json:ro \
  -e GOOGLE_APPLICATION_CREDENTIALS=/creds/credentials.json \
  ghcr.io/germaniu/ga4-seo-mcp
```

---

## 🩹 Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `This app is blocked` / `access_denied` en `gcloud ... login` | El cliente integrado de gcloud no puede pedir permisos de Analytics ni de Search Console. Usa tu propio cliente OAuth (`--client-id-file`) y agrégate como **Test User** en su pantalla de consentimiento: [docs/AUTH.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/docs/AUTH.md). |
| `cloud-platform scope is required but not requested` | Usa el comando que imprime `ga4-seo-mcp auth-command`: gcloud exige `cloud-platform` en la lista. El servidor nunca lo pide. |
| `403 ... API has not been used in project` | Habilita Google Analytics Admin API, Google Analytics Data API y Search Console API en tu proyecto de cuota y luego `gcloud auth application-default set-quota-project my-gcp-project`. |
| `403 ... does not have sufficient permissions for this property` | Agrega tu usuario (o el email de la cuenta de servicio) a la propiedad de GA4 o al sitio de Search Console. |
| `doctor` dice que al token le faltan permisos | Iniciaste sesión antes de activar un toolset o la escritura. Vuelve a ejecutar lo que imprime `auth-command`. |
| No aparecen las tools de escritura | Arranca el servidor con `--enable-writes`. Está apagado a propósito. |
| `PageSpeed Insights error 429` | La cuota anónima es compartida. Crea una API key y define `PAGESPEED_API_KEY`. |
| Los volúmenes de Keyword Planner salen redondeados (10, 30, 170, 210…) | Google Ads da volumen **por rangos** a las cuentas sin gasto activo. Usa el toolset `dataforseo` para números exactos. |
| Una propiedad borrada sigue apareciendo | `delete_property` es un borrado suave: Google la guarda en la papelera **35 días** (`list_properties(include_deleted=True)`). |
| HTTP responde `421 Invalid Host header` | Es la protección contra DNS rebinding. Conéctate con el host al que hiciste bind (`127.0.0.1`/`localhost` o la dirección de `MCP_HOST`); si escuchas en `0.0.0.0`, agrega la IP o nombre que usan tus clientes a `MCP_ALLOWED_HOSTS`. |
| HTTP responde `401` | Envía `Authorization: Bearer $MCP_AUTH_TOKEN`. |

---

## 📚 Documentación

- [docs/AUTH.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/docs/AUTH.md): cliente OAuth propio frente a cuenta de servicio, permisos por toolset y Test Users.
- [docs/TOOLS.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/docs/TOOLS.md): todas las tools y prompts, generado desde el registro.
- [docs/ARCHITECTURE.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/docs/ARCHITECTURE.md): módulos, registro y capas de seguridad.
- [SECURITY.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/SECURITY.md) · [CONTRIBUTING.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/CONTRIBUTING.md) · [CHANGELOG.md](https://github.com/GermaniU/ga4-seo-mcp/blob/main/CHANGELOG.md)

## 📄 Licencia

[MIT](https://github.com/GermaniU/ga4-seo-mcp/blob/main/LICENSE). Sin afiliación ni respaldo de Google. Google Analytics, Search Console y PageSpeed Insights son marcas de Google LLC.
