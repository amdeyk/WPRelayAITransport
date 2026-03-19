<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_server_ping() {
    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }

    return rest_ensure_response(array(
        'status' => 'ok',
        'site_url' => home_url('/'),
        'plugin_version' => WRS_PLUGIN_VERSION,
        'php_version' => PHP_VERSION,
        'wp_version' => get_bloginfo('version'),
        'modules' => $config['modules'] ?? array(),
    ));
}

function wrs_server_health() {
    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }
    $uploads = wp_get_upload_dir();
    $pages = get_posts(array(
        'post_type' => 'page',
        'posts_per_page' => 200,
        'post_status' => array('publish', 'draft', 'pending', 'private', 'future'),
        'meta_key' => '_wrs_managed',
    ));
    return rest_ensure_response(array(
        'status' => 'ok',
        'site_url' => home_url('/'),
        'plugin_version' => WRS_PLUGIN_VERSION,
        'php_version' => PHP_VERSION,
        'wp_version' => get_bloginfo('version'),
        'memory_limit' => ini_get('memory_limit'),
        'upload_dir' => $uploads['basedir'],
        'modules' => $config['modules'] ?? array(),
        'site_inventory' => array(
            'pages' => array_map(function ($page) {
                return array('id' => $page->ID, 'slug' => $page->post_name, 'title' => $page->post_title);
            }, $pages),
        ),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_server_errors() {
    return rest_ensure_response(array(
        'status' => 'ok',
        'last_error' => error_get_last(),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_server_db_status() {
    global $wpdb;
    return rest_ensure_response(array(
        'status' => 'ok',
        'prefix' => $wpdb->prefix,
        'has_connection' => !empty($wpdb->dbh),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_server_file_check() {
    return rest_ensure_response(array(
        'status' => 'ok',
        'config_path' => wrs_get_config_path(),
        'config_exists' => file_exists(wrs_get_config_path()),
        'storage_dir' => wrs_storage_dir(),
        'checkpoint_dir' => wrs_checkpoint_dir(),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_server_php_info() {
    return rest_ensure_response(array(
        'status' => 'ok',
        'php_version' => PHP_VERSION,
        'memory_limit' => ini_get('memory_limit'),
        'max_execution_time' => ini_get('max_execution_time'),
        'post_max_size' => ini_get('post_max_size'),
        'upload_max_filesize' => ini_get('upload_max_filesize'),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_setup_config(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $config = $params['config'] ?? null;
    if (!is_array($config)) {
        return new WP_Error('wrs_bad_config', 'Missing config payload.', array('status' => 400));
    }

    wrs_write_config($config);
    return rest_ensure_response(array(
        'success' => true,
        'message' => 'Configuration written to ' . wrs_get_config_path(),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_checkpoint_create_route(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $checkpoint = wrs_create_checkpoint(
        sanitize_text_field($params['op_id'] ?? ''),
        sanitize_text_field($params['op_type'] ?? ''),
        $params['targets'] ?? array()
    );

    return rest_ensure_response(array(
        'success' => true,
        'checkpoint' => $checkpoint,
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_checkpoint_list_route() {
    return rest_ensure_response(array(
        'success' => true,
        'checkpoints' => wrs_list_checkpoints(),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_checkpoint_get_route(WP_REST_Request $request) {
    $checkpoint = wrs_read_checkpoint(sanitize_text_field($request->get_param('checkpoint_id')));
    if (!$checkpoint) {
        return new WP_Error('wrs_checkpoint_missing', 'Checkpoint not found.', array('status' => 404));
    }
    return rest_ensure_response(array('success' => true, 'checkpoint' => $checkpoint, 'telemetry' => wrs_build_telemetry()));
}

function wrs_checkpoint_rollback_route(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $result = wrs_restore_checkpoint(sanitize_text_field($params['checkpoint_id'] ?? ''), !empty($params['dry_run']));
    if (is_wp_error($result)) {
        return $result;
    }
    return rest_ensure_response(array('success' => true, 'status' => 'SUCCESS', 'rollback' => $result, 'telemetry' => wrs_build_telemetry()));
}

// ── Pairing: permission check (no token/IP required — nonce is the auth) ────

function wrs_pair_permissions_check(WP_REST_Request $request) {
    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }

    if (!empty($config['require_https']) && !is_ssl()) {
        return new WP_Error('wrs_https_required', 'HTTPS is required.', array('status' => 403));
    }

    // Rate-limit pairing attempts per IP (max 5 per 15 min)
    $ip       = wrs_client_ip();
    $rate_key = 'wrs_pair_rate_' . md5($ip);
    $count    = (int) get_transient($rate_key);
    if ($count >= 5) {
        return new WP_Error('wrs_pair_rate_limited', 'Too many pairing attempts. Try again in 15 minutes.', array('status' => 429));
    }
    set_transient($rate_key, $count + 1, 15 * MINUTE_IN_SECONDS);

    return true;
}

// ── POST /wrs/v1/connect/pair ────────────────────────────────────────────────
// Accepts a one-time nonce from the WP admin panel, mints a fresh token,
// updates the server config, and returns the token to the CLI (single use).

function wrs_connect_pair(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $nonce  = sanitize_text_field((string) ($params['nonce'] ?? ''));

    if (empty($nonce)) {
        return new WP_Error('wrs_pair_missing_nonce', 'Nonce is required.', array('status' => 400));
    }

    $stored = get_transient('wrs_pair_nonce');
    if (!$stored || !hash_equals((string) $stored, $nonce)) {
        return new WP_Error('wrs_pair_invalid', 'Invalid or expired pairing code. Generate a new one in WordPress.', array('status' => 403));
    }

    // Single-use: delete immediately
    delete_transient('wrs_pair_nonce');

    // Generate a fresh 64-char hex token and bcrypt hash it
    $token      = bin2hex(random_bytes(32));
    $token_hash = password_hash($token, PASSWORD_BCRYPT);

    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }
    $config['token_hash'] = $token_hash;
    wrs_write_config($config);

    $modules = $config['modules'] ?? array();
    unset($modules['master_enabled']);

    return rest_ensure_response(array(
        'paired'    => true,
        'site_url'  => rtrim($config['site_url'], '/'),
        'site_name' => $config['site_name'],
        'token'     => $token,
        'page_mode' => $config['page_mode'] ?? 'html',
        'css_mode'  => $config['css_mode']  ?? 'inline',
        'modules'   => $modules,
    ));
}

// ── POST /wrs/v1/connect/revoke ──────────────────────────────────────────────
// Requires normal HMAC auth. Clears the token hash and disables master switch.

function wrs_connect_revoke(WP_REST_Request $request) {
    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }

    $config['token_hash']                = '';
    $config['modules']['master_enabled'] = false;
    wrs_write_config($config);
    delete_transient('wrs_pair_nonce');

    return rest_ensure_response(array(
        'revoked' => true,
        'message' => 'Token cleared and master switch disabled. Use the WP admin panel or re-run the setup wizard to reconnect.',
    ));
}

function wrs_register_routes() {
    register_rest_route('wrs/v1', '/connect/pair', array(
        'methods'             => WP_REST_Server::CREATABLE,
        'callback'            => 'wrs_connect_pair',
        'permission_callback' => 'wrs_pair_permissions_check',
    ));

    register_rest_route('wrs/v1', '/connect/revoke', array(
        'methods'             => WP_REST_Server::CREATABLE,
        'callback'            => 'wrs_connect_revoke',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/server/ping', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_server_ping',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/server/health', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_server_health',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/server/errors', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_server_errors',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/server/db-status', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_server_db_status',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/server/file-check', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_server_file_check',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/server/php-info', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_server_php_info',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/setup/config', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_setup_config',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/checkpoint/create', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_checkpoint_create_route',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/checkpoint/list', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_checkpoint_list_route',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/checkpoint/get', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_checkpoint_get_route',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/checkpoint/rollback', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_checkpoint_rollback_route',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/apply', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_apply_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/get', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_content_get_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/list', array(
        'methods' => WP_REST_Server::READABLE,
        'callback' => 'wrs_content_list_pages',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/publish', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_publish_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/update-css', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_update_css',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/clone', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_clone_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/set-image', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_set_image',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/set-meta', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_set_meta',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/delete', array(
        'methods' => WP_REST_Server::CREATABLE,
        'callback' => 'wrs_content_delete_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/inspect', array(
        'methods'             => WP_REST_Server::READABLE,
        'callback'            => 'wrs_content_inspect_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/adopt', array(
        'methods'             => WP_REST_Server::CREATABLE,
        'callback'            => 'wrs_content_adopt_page',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/elementor/get', array(
        'methods'             => WP_REST_Server::READABLE,
        'callback'            => 'wrs_content_elementor_get',
        'permission_callback' => 'wrs_permissions_check',
    ));

    register_rest_route('wrs/v1', '/content/page/elementor/set', array(
        'methods'             => WP_REST_Server::CREATABLE,
        'callback'            => 'wrs_content_elementor_set',
        'permission_callback' => 'wrs_permissions_check',
    ));
}
