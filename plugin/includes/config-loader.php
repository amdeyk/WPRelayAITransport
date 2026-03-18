<?php

if (!defined('ABSPATH')) {
    exit;
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

    $config = $decoded;
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
