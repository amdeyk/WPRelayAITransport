<?php
/**
 * Plugin Name: WP Remote Shell
 * Description: Authenticated CLI bridge for WordPress remote operations.
 * Version: 0.1.0
 * Author: WRS
 */

if (!defined('ABSPATH')) {
    exit;
}

define('WRS_PLUGIN_VERSION', '0.1.0');
define('WRS_PLUGIN_DIR', plugin_dir_path(__FILE__));

require_once WRS_PLUGIN_DIR . 'includes/config-loader.php';
require_once WRS_PLUGIN_DIR . 'includes/journal.php';
require_once WRS_PLUGIN_DIR . 'includes/telemetry.php';
require_once WRS_PLUGIN_DIR . 'includes/checkpoint.php';
require_once WRS_PLUGIN_DIR . 'includes/auth.php';
require_once WRS_PLUGIN_DIR . 'modules/content.php';
require_once WRS_PLUGIN_DIR . 'admin/settings-page.php';
require_once WRS_PLUGIN_DIR . 'includes/router.php';

function wrs_activate_plugin() {
    wrs_ensure_storage_dirs();
    wrs_install_runtime_config();
}

register_activation_hook(__FILE__, 'wrs_activate_plugin');

add_action('rest_api_init', 'wrs_register_routes');
add_action('admin_menu', 'wrs_register_settings_page');
add_filter('plugin_action_links_' . plugin_basename(__FILE__), 'wrs_plugin_action_links');

add_action('wp_head', function () {
    if (!is_singular('page')) {
        return;
    }

    $post_id = get_queried_object_id();
    $css = get_post_meta($post_id, '_wrs_css', true);
    if ($css) {
        echo "<style id=\"wrs-page-css\">\n" . $css . "\n</style>\n";
    }
}, 20);

add_action('wp_enqueue_scripts', function () {
    if (!is_singular('page')) {
        return;
    }

    $post_id = get_queried_object_id();
    $css_mode = get_post_meta($post_id, '_wrs_css_mode', true);
    $css_url = get_post_meta($post_id, '_wrs_css_url', true);
    if ($css_mode === 'enqueue' && $css_url) {
        wp_enqueue_style('wrs-page-' . $post_id, $css_url, array(), get_post_modified_time('U', true, $post_id));
    }
}, 20);

add_filter('template_include', function ($template) {
    if (!is_singular('page')) {
        return $template;
    }

    $post_id = get_queried_object_id();
    $canvas = get_post_meta($post_id, '_wrs_canvas', true);
    if ($canvas) {
        return WRS_PLUGIN_DIR . 'templates/wrs-canvas.php';
    }
    return $template;
});
