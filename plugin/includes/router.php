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

function wrs_register_routes() {
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
}
