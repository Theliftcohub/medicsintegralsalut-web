<?php
/**
 * form-handler.php — plantilla de manejador de formularios para producción (Plesk).
 *
 * Ver references/medicion-y-formularios.md para cómo se conecta desde <form action="/form-handler.php">
 * y qué NO hace este archivo en la previsualización de Netlify (allí no hay PHP: el formulario
 * debe desactivarse o avisar, nunca fallar en silencio; ver la variable PUBLIC_ENTORNO).
 *
 * Diseño (sin dependencias):
 * - Solo acepta POST; cualquier otro método -> 405.
 * - Honeypot: un campo oculto que un humano nunca rellena (ver HONEYPOT_FIELD abajo). Si llega
 *   relleno, se responde 303 igual que si hubiera ido bien (no delatar al bot) pero no se envía nada.
 * - Comprobación de origen: Origin o, si falta, Referer deben pertenecer al dominio del sitio.
 *   Sustituye a un token CSRF de sesión (aquí no hay sesiones/CMS) y es suficiente para un
 *   formulario público sin login.
 * - Límite básico por IP: como mucho MAX_ENVIOS_POR_VENTANA envíos por IP cada VENTANA_SEGUNDOS,
 *   contados en un archivo temporal (sys_get_temp_dir()). Es best-effort (se reinicia si se
 *   limpia /tmp); para algo más robusto, usa el rate-limit del propio Plesk/nginx.
 * - Envío por SMTP con un socket simple (sin PHPMailer): funciona en cualquier hosting con PHP
 *   estándar y evita depender de que mail() esté bien configurado (SPF/DKIM suele fallar con
 *   mail() nativo y el correo acaba en spam). Si el servidor permite Composer, PHPMailer es más
 *   robusto (maneja mejor TLS, adjuntos, codificaciones) — en ese caso sustituye smtp_enviar()
 *   por PHPMailer y dejamos aquí el fallback a mail() por si SMTP no está disponible.
 * - Credenciales SMTP fuera del repositorio: variables de entorno, o un archivo PHP fuera del
 *   document root que solo defina constantes y se incluye con require. Nunca hardcodeadas aquí.
 * - Autorespuesta opcional al remitente.
 * - Redirección 303 a la URL de "gracias" (evita el reenvío del POST al recargar y es la que
 *   dispara la conversión en GA4/Ads, ver medicion-y-formularios.md).
 * - Registro mínimo de errores con error_log() (va al log de error de PHP de Plesk, no a un
 *   archivo público).
 */

declare(strict_types=1);

// ---------------------------------------------------------------------------
// Configuración del formulario. Ajusta esto por cliente/proyecto.
// ---------------------------------------------------------------------------
const DOMINIO_PERMITIDO   = 'medicsintegralsalut.com'; // sin esquema, sin www
const URL_GRACIAS         = '/gracias/';
const HONEYPOT_FIELD      = 'website';                 // input oculto por CSS, nunca por "display:none" solo (usa además tabindex="-1" y aria-hidden)
const CAMPOS_OBLIGATORIOS = []; // Medics: formularios distintos; basta teléfono O email (ver paso 5)
const MAX_ENVIOS_POR_VENTANA = 5;
const VENTANA_SEGUNDOS       = 600; // 10 minutos
// Destinatario del aviso por email: variable de entorno FORM_DESTINATARIO en Plesk (pendiente de confirmar con la clínica).
define('DESTINATARIO', getenv('FORM_DESTINATARIO') ?: (defined('FORM_DESTINATARIO') ? FORM_DESTINATARIO : 'info@' . DOMINIO_PERMITIDO));
const AUTORRESPUESTA_ACTIVA  = false; // la clínica confirma si quiere autorrespuesta (hoy CF7 no consta que la envíe)
const AUTORRESPUESTA_ASUNTO  = 'Hemos recibido tu mensaje';
const AUTORRESPUESTA_TEXTO   = "Gracias por escribirnos. Te responderemos lo antes posible.";

// Credenciales SMTP: fuera del repositorio. Prioridad: variables de entorno del hosting
// (recomendado en Plesk: pestaña "Variables de entorno PHP" del dominio); si no existen,
// se intenta un archivo fuera del document root (p. ej. un nivel por encima de httpdocs/).
// Nunca poner usuario/contraseña reales en este archivo ni hacer commit de secrets/smtp.php.
$smtp_config_externo = dirname(__DIR__, 2) . '/secrets/smtp.php'; // ajusta la ruta a tu Plesk
if (is_readable($smtp_config_externo)) {
    require $smtp_config_externo; // debe definir SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SEGURIDAD
}
$SMTP_HOST = getenv('SMTP_HOST') ?: (defined('SMTP_HOST') ? SMTP_HOST : null);
$SMTP_PORT = (int) (getenv('SMTP_PORT') ?: (defined('SMTP_PORT') ? SMTP_PORT : 587));
$SMTP_USER = getenv('SMTP_USER') ?: (defined('SMTP_USER') ? SMTP_USER : null);
$SMTP_PASS = getenv('SMTP_PASS') ?: (defined('SMTP_PASS') ? SMTP_PASS : null);
$SMTP_SEGURIDAD = getenv('SMTP_SEGURIDAD') ?: (defined('SMTP_SEGURIDAD') ? SMTP_SEGURIDAD : 'tls'); // tls|ssl

// ---------------------------------------------------------------------------
// 1) Solo POST
// ---------------------------------------------------------------------------
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    http_response_code(405);
    header('Allow: POST');
    exit('Método no permitido.');
}

// ---------------------------------------------------------------------------
// 2) Origen: Origin (o Referer si falta) debe ser del propio dominio
// ---------------------------------------------------------------------------
function origen_valido(): bool
{
    $origen = $_SERVER['HTTP_ORIGIN'] ?? '';
    $referer = $_SERVER['HTTP_REFERER'] ?? '';
    $candidato = $origen ?: $referer;
    if ($candidato === '') {
        return false; // sin Origin ni Referer: probablemente no viene de un navegador real
    }
    $host = parse_url($candidato, PHP_URL_HOST) ?? '';
    $host = strtolower(preg_replace('/^www\./', '', $host));
    return $host === strtolower(DOMINIO_PERMITIDO);
}

if (!origen_valido()) {
    http_response_code(403);
    exit('Origen no permitido.');
}

// ---------------------------------------------------------------------------
// 3) Honeypot: si el campo trampa viene relleno, es un bot. Respondemos "bien" sin enviar nada.
// ---------------------------------------------------------------------------
$es_bot = trim((string) ($_POST[HONEYPOT_FIELD] ?? '')) !== '';

// ---------------------------------------------------------------------------
// 4) Límite básico por IP (best-effort, archivo temporal)
// ---------------------------------------------------------------------------
function limite_superado(string $ip): bool
{
    $archivo = sys_get_temp_dir() . '/formhandler_' . md5($ip) . '.json';
    $ahora = time();
    $envios = [];
    if (is_readable($archivo)) {
        $envios = json_decode((string) file_get_contents($archivo), true) ?: [];
    }
    $envios = array_values(array_filter($envios, fn($t) => $ahora - $t < VENTANA_SEGUNDOS));
    if (count($envios) >= MAX_ENVIOS_POR_VENTANA) {
        return true;
    }
    $envios[] = $ahora;
    @file_put_contents($archivo, json_encode($envios));
    return false;
}

$ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
if (!$es_bot && limite_superado($ip)) {
    http_response_code(429);
    exit('Demasiados envíos. Inténtalo más tarde.');
}

// ---------------------------------------------------------------------------
// 5) Validación y saneado de campos
// ---------------------------------------------------------------------------
function limpiar(string $v): string
{
    return trim(strip_tags($v));
}

$datos = [];
foreach ($_POST as $clave => $valor) {
    if ($clave === HONEYPOT_FIELD || is_array($valor)) {
        continue;
    }
    $datos[$clave] = limpiar((string) $valor);
}

$errores = [];
foreach (CAMPOS_OBLIGATORIOS as $campo) {
    if (empty($datos[$campo])) {
        $errores[] = "Falta el campo obligatorio: {$campo}";
    }
}
if (empty($datos['telefono']) && empty($datos['email'])) {
    $errores[] = 'Indica un teléfono o un email';
}
if (!empty($datos['email']) && !filter_var($datos['email'], FILTER_VALIDATE_EMAIL)) {
    $errores[] = 'Email no válido';
}

if ($errores && !$es_bot) {
    http_response_code(422);
    exit(implode("\n", $errores));
}

// ---------------------------------------------------------------------------
// 6) Envío por SMTP (socket simple, sin dependencias). Si no hay SMTP configurado,
//    fallback a mail() — documentado como peor entregabilidad, ver cabecera del archivo.
// ---------------------------------------------------------------------------
function smtp_enviar(string $host, int $port, string $usuario, string $clave, string $seguridad,
                      string $de, string $para, string $asunto, string $cuerpo, ?string $responder_a = null): bool
{
    $transporte = $seguridad === 'ssl' ? "ssl://{$host}" : $host;
    $fp = @stream_socket_client("{$transporte}:{$port}", $errno, $errstr, 15);
    if (!$fp) {
        error_log("form-handler SMTP: no se pudo conectar a {$host}:{$port} ({$errstr})");
        return false;
    }
    $leer = function () use ($fp) {
        $linea = fgets($fp, 512);
        return $linea === false ? '' : $linea;
    };
    $escribir = function (string $cmd) use ($fp) {
        fwrite($fp, $cmd . "\r\n");
    };
    $leer();
    $escribir('EHLO ' . DOMINIO_PERMITIDO);
    $leer();
    if ($seguridad === 'tls') {
        $escribir('STARTTLS');
        $leer();
        stream_socket_enable_crypto($fp, true, STREAM_CRYPTO_METHOD_TLS_CLIENT);
        $escribir('EHLO ' . DOMINIO_PERMITIDO);
        $leer();
    }
    $escribir('AUTH LOGIN');
    $leer();
    $escribir(base64_encode($usuario));
    $leer();
    $escribir(base64_encode($clave));
    $resp = $leer();
    if (strpos($resp, '235') !== 0) {
        error_log('form-handler SMTP: autenticación rechazada');
        fclose($fp);
        return false;
    }
    $escribir("MAIL FROM:<{$de}>");
    $leer();
    $escribir("RCPT TO:<{$para}>");
    $leer();
    $escribir('DATA');
    $leer();
    $cabeceras = "From: {$de}\r\nTo: {$para}\r\nSubject: {$asunto}\r\n"
        . ($responder_a ? "Reply-To: {$responder_a}\r\n" : '')
        . "MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n";
    $escribir($cabeceras . $cuerpo . "\r\n.");
    $resp = $leer();
    $escribir('QUIT');
    fclose($fp);
    return strpos($resp, '250') === 0;
}

// ---------------------------------------------------------------------------
// 5b) Medics: alta del lead en Kommo vía n8n (workflow 4oQdrYDIlqEjaKpK "Web Medics · Formularios web").
//     URL y token SOLO en variables de entorno de Plesk o en secrets/smtp.php (fuera del document root):
//     N8N_FORM_URL, N8N_FORM_TOKEN. Si n8n falla, el email sigue saliendo y se registra en error_log.
// ---------------------------------------------------------------------------
$N8N_URL   = getenv('N8N_FORM_URL') ?: (defined('N8N_FORM_URL') ? N8N_FORM_URL : null);
$N8N_TOKEN = getenv('N8N_FORM_TOKEN') ?: (defined('N8N_FORM_TOKEN') ? N8N_FORM_TOKEN : null);
$pagina = $_SERVER['HTTP_REFERER'] ?? '';
$kommo_ok = false;
$payload = $datos + ['pagina' => $pagina, 'formulario' => $datos['_form'] ?? '', 'idioma' => $datos['_lang'] ?? ''];
if (!$es_bot && $N8N_URL && $N8N_TOKEN) {
    $ch = curl_init($N8N_URL);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($payload, JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'x-mis-token: ' . $N8N_TOKEN],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 8,
    ]);
    $res = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    $kommo_ok = !($res === false || $code >= 300);
    if (!$kommo_ok) {
        error_log("form-handler: n8n respondió {$code} — el lead NO ha entrado en Kommo");
    }
} elseif (!$es_bot) {
    error_log('form-handler: N8N_FORM_URL/N8N_FORM_TOKEN sin configurar — el lead NO entra en Kommo');
}

$cuerpo = "Nuevo mensaje desde " . DOMINIO_PERMITIDO . ":\n\n";
foreach ($datos as $clave => $valor) {
    $cuerpo .= "{$clave}: {$valor}\n";
}
$cuerpo .= "\nIP: {$ip}\n";

$enviado = false;
// Medics (decisión Oscar 27/09/2026): el destino es Kommo; la autorrespuesta la da Kommo al entrar el lead.
// El email solo sale como RESPALDO si n8n/Kommo falla y FORM_DESTINATARIO está configurado en Plesk.
$enviar_respaldo = !$kommo_ok && (getenv('FORM_DESTINATARIO') || defined('FORM_DESTINATARIO'));
if (!$es_bot && $enviar_respaldo) {
    if ($SMTP_HOST && $SMTP_USER && $SMTP_PASS) {
        $enviado = smtp_enviar($SMTP_HOST, $SMTP_PORT, $SMTP_USER, $SMTP_PASS, $SMTP_SEGURIDAD,
            $SMTP_USER, DESTINATARIO, '[RESPALDO: no entró en Kommo] Nuevo lead web Medics', $cuerpo, $datos['email'] ?? null);
    }
    if (!$enviado) {
        // Fallback: mail() nativo. Peor entregabilidad (SPF/DKIM), pero mejor que no enviar nada.
        $cabeceras = 'From: ' . DESTINATARIO . "\r\n" . (empty($datos['email']) ? '' : "Reply-To: {$datos['email']}\r\n");
        $enviado = @mail(DESTINATARIO, '[RESPALDO: no entró en Kommo] Nuevo lead web Medics', $cuerpo, $cabeceras);
        if (!$enviado) {
            error_log('form-handler: fallo al enviar tanto por SMTP como por mail()');
        }
    }

    if ($enviado && AUTORRESPUESTA_ACTIVA && !empty($datos['email'])) {
        if ($SMTP_HOST && $SMTP_USER && $SMTP_PASS) {
            smtp_enviar($SMTP_HOST, $SMTP_PORT, $SMTP_USER, $SMTP_PASS, $SMTP_SEGURIDAD,
                DESTINATARIO, $datos['email'], AUTORRESPUESTA_ASUNTO, AUTORRESPUESTA_TEXTO);
        } else {
            @mail($datos['email'], AUTORRESPUESTA_ASUNTO, AUTORRESPUESTA_TEXTO, 'From: ' . DESTINATARIO . "\r\n");
        }
    }
}

// ---------------------------------------------------------------------------
// 7) Redirección 303: evita reenvío del POST y es la que dispara la conversión en
//    GA4/Ads al cargar la página de gracias (ver medicion-y-formularios.md).
// ---------------------------------------------------------------------------
// Página de gracias por idioma/formulario (campo oculto _gracias): solo rutas internas, nunca URLs externas.
$gracias = $datos['_gracias'] ?? '';
if (!preg_match('#^/(?!/)[^\s]*$#', $gracias)) {
    $gracias = URL_GRACIAS;
}
header('Location: ' . $gracias, true, 303);
exit;
