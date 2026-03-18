<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_build_telemetry($extra = array(), $warnings = array()) {
    $telemetry = array(
        'php_errors' => array(),
        'warnings' => $warnings,
        'memory_peak_bytes' => memory_get_peak_usage(true),
        'server_timestamp' => gmdate('c'),
        'wp_version' => get_bloginfo('version'),
        'db_rows_affected' => 0,
        'content_echo' => '',
        'post_status_after' => '',
        'wrote_files' => array(),
        'recovery_hint' => 'NONE',
    );

    $last_error = error_get_last();
    if ($last_error) {
        $telemetry['php_errors'][] = $last_error;
    }

    return array_merge($telemetry, $extra);
}


function wrs_recovery_hint($retryable, $reason = '') {
    return array(
        'type' => $retryable ? 'SAFE_TO_RETRY' : 'DO_NOT_RETRY',
        'reason' => $reason,
    );
}
