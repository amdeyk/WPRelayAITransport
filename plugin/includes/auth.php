<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_client_ip() {
    $keys = array('HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR');
    foreach ($keys as $key) {
        if (!empty($_SERVER[$key])) {
            $parts = explode(',', wp_unslash($_SERVER[$key]));
            return trim($parts[0]);
        }
    }
    return '';
}

function wrs_sort_recursive($value) {
    if (!is_array($value)) {
        return $value;
    }

    if (array_keys($value) !== range(0, count($value) - 1)) {
        ksort($value);
    }

    foreach ($value as $key => $child) {
        $value[$key] = wrs_sort_recursive($child);
    }
    return $value;
}

function wrs_rate_limit_key($ip) {
    return 'wrs_rate_' . md5($ip);
}

function wrs_replay_key($signature) {
    return 'wrs_replay_' . md5($signature);
}

function wrs_command_blocklist_patterns() {
    return array(
        'rm -rf /',
        'mkfs',
        'dd if=/dev/zero',
        'shutdown -h',
        'reboot',
        ':(){:|:&};:',
    );
}

function wrs_command_is_blocked($command) {
    foreach (wrs_command_blocklist_patterns() as $pattern) {
        if (stripos($command, $pattern) !== false) {
            return true;
        }
    }
    return false;
}

function wrs_verify_signature($token, WP_REST_Request $request) {
    $route = str_replace('/wrs/v1', '', $request->get_route());
    $timestamp = $request->get_header('x-wrs-time');
    $payload = $request->get_json_params();
    if (empty($payload)) {
        $payload = $request->get_query_params();
    }
    $payload_json = '';
    if (!empty($payload)) {
        $payload_json = wp_json_encode(wrs_sort_recursive($payload), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    }

    $message = $route . '|' . $timestamp . '|' . $payload_json;
    $expected = hash_hmac('sha256', $message, $token);
    $signature = (string) $request->get_header('x-wrs-signature');

    return hash_equals($expected, $signature);
}

function wrs_permissions_check(WP_REST_Request $request) {
    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }

    if (empty($config['modules']['master_enabled'])) {
        return new WP_Error('wrs_disabled', 'WRS is disabled.', array('status' => 404));
    }

    if (!empty($config['require_https']) && !is_ssl()) {
        return new WP_Error('wrs_https_required', 'HTTPS is required.', array('status' => 403));
    }

    $ip = wrs_client_ip();
    $allowed_ips = $config['allowed_ips'] ?? array();
    if (!in_array($ip, $allowed_ips, true)) {
        return new WP_Error('wrs_ip_denied', 'IP address is not allowlisted.', array('status' => 403));
    }

    $count = (int) get_transient(wrs_rate_limit_key($ip));
    $limit = (int) ($config['rate_limit_per_minute'] ?? 20);
    if ($count >= $limit) {
        return new WP_Error('wrs_rate_limited', 'Rate limit exceeded.', array('status' => 429));
    }
    set_transient(wrs_rate_limit_key($ip), $count + 1, MINUTE_IN_SECONDS);

    $token = (string) $request->get_header('x-wrs-token');
    if (!$token || empty($config['token_hash']) || !password_verify($token, $config['token_hash'])) {
        return new WP_Error('wrs_invalid_token', 'Invalid token.', array('status' => 403));
    }

    $timestamp = (int) $request->get_header('x-wrs-time');
    $window = (int) ($config['replay_window_seconds'] ?? 30);
    if (!$timestamp || abs(time() - $timestamp) > $window) {
        return new WP_Error('wrs_replay_window', 'Timestamp outside replay window.', array('status' => 403));
    }

    if (!wrs_verify_signature($token, $request)) {
        return new WP_Error('wrs_bad_signature', 'HMAC verification failed.', array('status' => 403));
    }

    $signature = (string) $request->get_header('x-wrs-signature');
    if (get_transient(wrs_replay_key($signature))) {
        return new WP_Error('wrs_replay_detected', 'Replay detected.', array('status' => 403));
    }
    set_transient(wrs_replay_key($signature), 1, $window);

    return true;
}
