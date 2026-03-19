<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_config_defaults() {
    return array(
        'site_name' => '',
        'site_url' => '',
        'token_hash' => '',
        'allow_all_ips' => false,
        'allowed_ips' => array(),
        'require_https' => true,
        'replay_window_seconds' => 30,
        'rate_limit_per_minute' => 20,
        'max_output_bytes' => 524288,
        'exec_timeout_seconds' => 30,
        'page_mode' => 'html',
        'css_mode' => 'inline',
        'modules' => array(
            'master_enabled' => true,
            'content' => true,
            'media' => true,
            'database' => true,
            'members' => false,
            'email' => false,
            'forms' => false,
            'woocommerce' => false,
            'cpt' => false,
            'cron' => false,
        ),
        'telemetry' => array(
            'capture_php_errors' => true,
            'capture_memory' => true,
        ),
        'checkpoint' => array(
            'enabled' => true,
        ),
        'journal' => array(
            'enabled' => true,
        ),
        'log_retention_count' => 500,
    );
}

function wrs_merge_config_values($defaults, $value) {
    if (!is_array($defaults) || !is_array($value)) {
        return $value;
    }

    $merged = $defaults;
    foreach ($value as $key => $child) {
        if (array_key_exists($key, $defaults)) {
            $merged[$key] = wrs_merge_config_values($defaults[$key], $child);
        } else {
            $merged[$key] = $child;
        }
    }
    return $merged;
}

function wrs_default_config_path() {
    $uploads = wp_get_upload_dir();
    return trailingslashit($uploads['basedir']) . 'wrs/plugin.config.json';
}

function wrs_get_config_path() {
    if (defined('WRS_CONFIG_PATH') && WRS_CONFIG_PATH) {
        return WRS_CONFIG_PATH;
    }
    return wrs_default_config_path();
}

function wrs_runtime_config_path() {
    return WRS_PLUGIN_DIR . 'runtime/plugin.config.json';
}

function wrs_storage_dir() {
    $path = trailingslashit(dirname(wrs_get_config_path()));
    if (substr($path, -4) !== 'wrs/') {
        $path .= 'wrs/';
    }
    return $path;
}

function wrs_ensure_storage_dirs() {
    wp_mkdir_p(wrs_storage_dir());
    wp_mkdir_p(wrs_storage_dir() . 'checkpoints');
}

function wrs_install_runtime_config() {
    $target = wrs_get_config_path();
    $runtime = wrs_runtime_config_path();
    if (file_exists($target) || !file_exists($runtime)) {
        return;
    }

    wrs_ensure_storage_dirs();
    wp_mkdir_p(dirname($target));
    copy($runtime, $target);
}

function wrs_get_config() {
    static $config = null;
    if ($config !== null) {
        return $config;
    }

    $path = wrs_get_config_path();
    if (!file_exists($path)) {
        return new WP_Error('wrs_config_missing', 'WRS config file is missing.', array('status' => 500));
    }

    $decoded = json_decode(file_get_contents($path), true);
    if (!is_array($decoded)) {
        return new WP_Error('wrs_config_invalid', 'WRS config file is invalid JSON.', array('status' => 500));
    }

    $config = wrs_merge_config_values(wrs_config_defaults(), $decoded);
    return $config;
}

function wrs_write_config($config) {
    wrs_ensure_storage_dirs();
    $path = wrs_get_config_path();
    wp_mkdir_p(dirname($path));
    $encoded = wp_json_encode($config, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    file_put_contents($path, $encoded . PHP_EOL, LOCK_EX);
    return true;
}
