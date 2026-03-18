<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_register_settings_page() {
    add_management_page(
        'WP Remote Shell',
        'WP Remote Shell',
        'manage_options',
        'wp-remote-shell',
        'wrs_render_settings_page'
    );
}

function wrs_render_settings_page() {
    $config = wrs_get_config();
    ?>
    <div class="wrap">
        <h1>WP Remote Shell</h1>
        <p><strong>Config path:</strong> <?php echo esc_html(wrs_get_config_path()); ?></p>
        <p><strong>Storage dir:</strong> <?php echo esc_html(wrs_storage_dir()); ?></p>
        <h2>Config</h2>
        <pre><?php echo esc_html(is_wp_error($config) ? $config->get_error_message() : wp_json_encode($config, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)); ?></pre>
    </div>
    <?php
}

