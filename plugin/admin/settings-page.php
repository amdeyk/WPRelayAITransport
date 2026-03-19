<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_register_settings_page() {
    add_menu_page(
        'WP Remote Shell',
        'WP Remote Shell',
        'manage_options',
        'wp-remote-shell',
        'wrs_render_settings_page',
        'dashicons-admin-tools',
        58
    );
}

function wrs_plugin_action_links($links) {
    $settings_link = sprintf(
        '<a href="%s">%s</a>',
        esc_url(admin_url('admin.php?page=wp-remote-shell')),
        esc_html__('Settings')
    );

    array_unshift($links, $settings_link);
    return $links;
}

function wrs_admin_module_labels() {
    return array(
        'content' => 'Content',
        'media' => 'Media',
        'database' => 'Database',
        'members' => 'Members',
        'email' => 'Email',
        'forms' => 'Forms',
        'woocommerce' => 'WooCommerce',
        'cpt' => 'Custom Post Types',
        'cron' => 'Cron',
    );
}

function wrs_admin_checkbox_value($key) {
    return !empty($_POST[$key]);
}

function wrs_admin_int_value($key, $default, $minimum, $maximum) {
    if (!isset($_POST[$key])) {
        return $default;
    }

    $value = (int) wp_unslash($_POST[$key]);
    if ($value < $minimum) {
        return $minimum;
    }
    if ($value > $maximum) {
        return $maximum;
    }
    return $value;
}

function wrs_admin_list_value($key) {
    if (!isset($_POST[$key])) {
        return array();
    }

    $raw = trim((string) wp_unslash($_POST[$key]));
    if ($raw === '') {
        return array();
    }

    $items = preg_split('/[\r\n,]+/', $raw);
    $clean = array();
    foreach ($items as $item) {
        $item = trim($item);
        if ($item === '') {
            continue;
        }
        $clean[$item] = $item;
    }
    return array_values($clean);
}

function wrs_admin_apply_access_preset($config) {
    $preset = sanitize_text_field((string) wp_unslash($_POST['wrs_access_preset'] ?? ''));
    $current_ip = wrs_client_ip();

    if ($preset === 'allow_all') {
        $config['allow_all_ips'] = true;
        return $config;
    }

    if ($preset === 'current_ip') {
        if ($current_ip === '') {
            return new WP_Error('wrs_admin_ip_missing', 'Could not detect the current admin IP for this request.');
        }
        $config['allow_all_ips'] = false;
        $config['allowed_ips'] = array($current_ip);
        return $config;
    }

    if ($preset === 'append_current_ip') {
        if ($current_ip === '') {
            return new WP_Error('wrs_admin_ip_missing', 'Could not detect the current admin IP for this request.');
        }
        $config['allowed_ips'][] = $current_ip;
        $config['allowed_ips'] = array_values(array_unique($config['allowed_ips']));
        return $config;
    }

    return $config;
}

function wrs_admin_checklist_items($config) {
    $current_ip = wrs_client_ip();
    $restricted_with_current_ip = !empty($config['allow_all_ips']) || in_array($current_ip, $config['allowed_ips'], true);

    return array(
        array(
            'label' => 'Config file is available',
            'done' => file_exists(wrs_get_config_path()),
            'detail' => wrs_get_config_path(),
        ),
        array(
            'label' => 'Token hash is configured',
            'done' => !empty($config['token_hash']),
            'detail' => !empty($config['token_hash']) ? 'Authenticated requests are enabled.' : 'Token hash is missing.',
        ),
        array(
            'label' => 'Transport is enabled',
            'done' => !empty($config['modules']['master_enabled']),
            'detail' => !empty($config['modules']['master_enabled']) ? 'API can accept requests.' : 'Master switch is disabled.',
        ),
        array(
            'label' => 'Novice setup path is open',
            'done' => !empty($config['allow_all_ips']) || $restricted_with_current_ip,
            'detail' => !empty($config['allow_all_ips']) ? 'All IPs are allowed during setup.' : ($restricted_with_current_ip ? 'Current admin IP is allowed.' : 'Current admin IP is not in the allowlist.'),
        ),
    );
}

function wrs_handle_pair_code_generation() {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST' || empty($_POST['wrs_generate_pair'])) {
        return;
    }

    if (!current_user_can('manage_options')) {
        return;
    }

    check_admin_referer('wrs_gen_pair');

    // 16 random bytes → 32-char hex nonce, stored for 30 min (single-use enforced by the endpoint)
    $nonce  = bin2hex(random_bytes(16));
    set_transient('wrs_pair_nonce', $nonce, 30 * MINUTE_IN_SECONDS);

    $redirect_url = add_query_arg(
        array('page' => 'wp-remote-shell', 'wrs-pair-ready' => '1'),
        admin_url('admin.php')
    );
    wp_safe_redirect($redirect_url);
    exit;
}

function wrs_get_current_pair_code() {
    $nonce = get_transient('wrs_pair_nonce');
    if (!$nonce) {
        return null;
    }
    // Encode as hex(JSON{u, n}) so the CLI can decode URL + nonce from one string
    $bundle = json_encode(array('u' => rtrim(home_url('/'), '/'), 'n' => $nonce));
    return bin2hex($bundle);
}

function wrs_handle_settings_page_submission() {
    if ($_SERVER['REQUEST_METHOD'] !== 'POST' || empty($_POST['wrs_settings_submit'])) {
        return null;
    }

    if (!current_user_can('manage_options')) {
        return new WP_Error('wrs_admin_forbidden', 'You do not have permission to update WP Remote Shell settings.');
    }

    check_admin_referer('wrs_save_settings');

    $config = wrs_get_config();
    if (is_wp_error($config)) {
        return $config;
    }

    $config['site_name'] = sanitize_text_field((string) wp_unslash($_POST['site_name'] ?? $config['site_name']));
    $config['site_url'] = esc_url_raw((string) wp_unslash($_POST['site_url'] ?? $config['site_url']));
    $config['allow_all_ips'] = wrs_admin_checkbox_value('allow_all_ips');
    $config['allowed_ips'] = wrs_admin_list_value('allowed_ips');
    $config['require_https'] = wrs_admin_checkbox_value('require_https');
    $config = wrs_admin_apply_access_preset($config);
    if (is_wp_error($config)) {
        return $config;
    }
    if (empty($config['allow_all_ips']) && empty($config['allowed_ips'])) {
        return new WP_Error('wrs_admin_allowlist_required', 'Add at least one allowed IP or keep "Allow all IPs during setup" enabled.');
    }
    $config['page_mode'] = in_array($_POST['page_mode'] ?? 'html', array('html', 'elementor'), true)
        ? sanitize_text_field((string) wp_unslash($_POST['page_mode']))
        : 'html';
    $config['css_mode'] = in_array($_POST['css_mode'] ?? 'inline', array('inline', 'enqueue'), true)
        ? sanitize_text_field((string) wp_unslash($_POST['css_mode']))
        : 'inline';
    $config['replay_window_seconds'] = wrs_admin_int_value('replay_window_seconds', 30, 5, 3600);
    $config['rate_limit_per_minute'] = wrs_admin_int_value('rate_limit_per_minute', 20, 1, 10000);
    $config['exec_timeout_seconds'] = wrs_admin_int_value('exec_timeout_seconds', 30, 1, 600);
    $config['max_output_bytes'] = wrs_admin_int_value('max_output_bytes', 524288, 1024, 10485760);
    $config['log_retention_count'] = wrs_admin_int_value('log_retention_count', 500, 10, 50000);

    $config['modules']['master_enabled'] = wrs_admin_checkbox_value('module_master_enabled');
    foreach (array_keys(wrs_admin_module_labels()) as $module_key) {
        $config['modules'][$module_key] = wrs_admin_checkbox_value('module_' . $module_key);
    }

    $config['checkpoint']['enabled'] = wrs_admin_checkbox_value('checkpoint_enabled');
    $config['journal']['enabled'] = wrs_admin_checkbox_value('journal_enabled');
    $config['telemetry']['capture_php_errors'] = wrs_admin_checkbox_value('telemetry_capture_php_errors');
    $config['telemetry']['capture_memory'] = wrs_admin_checkbox_value('telemetry_capture_memory');

    wrs_write_config($config);

    $redirect_url = add_query_arg(
        array(
            'page' => 'wp-remote-shell',
            'wrs-updated' => '1',
        ),
        admin_url('admin.php')
    );
    wp_safe_redirect($redirect_url);
    exit;
}

function wrs_render_toggle_row($name, $label, $checked, $description) {
    ?>
    <label class="wrs-toggle-row" for="<?php echo esc_attr($name); ?>">
        <span class="wrs-toggle-copy">
            <strong><?php echo esc_html($label); ?></strong>
            <small><?php echo esc_html($description); ?></small>
        </span>
        <span class="wrs-switch">
            <input type="checkbox" id="<?php echo esc_attr($name); ?>" name="<?php echo esc_attr($name); ?>" value="1" <?php checked($checked); ?> />
            <span class="wrs-switch-ui" aria-hidden="true"></span>
        </span>
    </label>
    <?php
}

function wrs_render_settings_page() {
    wrs_handle_pair_code_generation();
    $save_error = wrs_handle_settings_page_submission();
    $config = wrs_get_config();

    ?>
    <div class="wrap wrs-admin-page">
        <style>
            .wrs-admin-page {
                max-width: 1180px;
            }
            .wrs-admin-page .wrs-shell {
                margin-top: 20px;
                display: grid;
                gap: 20px;
            }
            .wrs-admin-page .wrs-hero {
                display: grid;
                grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.9fr);
                gap: 18px;
                padding: 24px;
                border-radius: 18px;
                background: linear-gradient(135deg, #10243e 0%, #1d4f6b 55%, #edf7f6 100%);
                color: #fff;
                box-shadow: 0 18px 40px rgba(16, 36, 62, 0.15);
            }
            .wrs-admin-page .wrs-hero h1 {
                margin: 0 0 8px;
                color: #fff;
                font-size: 30px;
                line-height: 1.15;
            }
            .wrs-admin-page .wrs-hero p {
                margin: 0;
                font-size: 15px;
                line-height: 1.6;
                max-width: 720px;
            }
            .wrs-admin-page .wrs-status-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 12px;
            }
            .wrs-admin-page .wrs-stat {
                padding: 14px;
                border-radius: 14px;
                background: rgba(255, 255, 255, 0.12);
                backdrop-filter: blur(10px);
            }
            .wrs-admin-page .wrs-stat span {
                display: block;
                font-size: 11px;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                opacity: 0.78;
                margin-bottom: 6px;
            }
            .wrs-admin-page .wrs-stat strong,
            .wrs-admin-page .wrs-stat code {
                color: #fff;
                word-break: break-word;
            }
            .wrs-admin-page .wrs-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 20px;
            }
            .wrs-admin-page .wrs-checklist {
                display: grid;
                gap: 12px;
            }
            .wrs-admin-page .wrs-check-item {
                display: flex;
                align-items: flex-start;
                gap: 12px;
                padding: 14px 16px;
                border: 1px solid #d9e5eb;
                border-radius: 14px;
                background: #f8fbfc;
            }
            .wrs-admin-page .wrs-check-mark {
                width: 26px;
                height: 26px;
                border-radius: 50%;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                font-weight: 700;
                font-size: 14px;
                flex: 0 0 auto;
                background: #cfdde4;
                color: #395261;
            }
            .wrs-admin-page .wrs-check-item.is-done .wrs-check-mark {
                background: #1f7a5c;
                color: #fff;
            }
            .wrs-admin-page .wrs-check-copy {
                display: grid;
                gap: 4px;
            }
            .wrs-admin-page .wrs-check-copy strong {
                font-size: 14px;
            }
            .wrs-admin-page .wrs-check-copy small {
                color: #5b7384;
                line-height: 1.45;
                word-break: break-word;
            }
            .wrs-admin-page .wrs-card {
                background: #fff;
                border: 1px solid #d6e3ea;
                border-radius: 18px;
                padding: 22px;
                box-shadow: 0 10px 28px rgba(17, 43, 60, 0.06);
            }
            .wrs-admin-page .wrs-card.wrs-card-full {
                grid-column: 1 / -1;
            }
            .wrs-admin-page .wrs-card h2 {
                margin: 0 0 6px;
                font-size: 19px;
            }
            .wrs-admin-page .wrs-card > p {
                margin-top: 0;
                color: #4c6475;
            }
            .wrs-admin-page .wrs-field-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 14px;
            }
            .wrs-admin-page .wrs-field {
                display: grid;
                gap: 6px;
            }
            .wrs-admin-page .wrs-field.wrs-field-full {
                grid-column: 1 / -1;
            }
            .wrs-admin-page .wrs-field label {
                font-weight: 600;
            }
            .wrs-admin-page .wrs-field input[type="text"],
            .wrs-admin-page .wrs-field input[type="number"],
            .wrs-admin-page .wrs-field input[type="url"],
            .wrs-admin-page .wrs-field select,
            .wrs-admin-page .wrs-field textarea {
                width: 100%;
                min-height: 42px;
                border: 1px solid #c6d6df;
                border-radius: 12px;
                padding: 10px 12px;
                box-shadow: inset 0 1px 2px rgba(17, 43, 60, 0.04);
            }
            .wrs-admin-page .wrs-field textarea {
                min-height: 120px;
                resize: vertical;
            }
            .wrs-admin-page .wrs-field small {
                color: #5f7687;
            }
            .wrs-admin-page .wrs-toggle-list {
                display: grid;
                gap: 12px;
            }
            .wrs-admin-page .wrs-action-row {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-top: 14px;
            }
            .wrs-admin-page .wrs-action-row .button {
                min-height: 38px;
            }
            .wrs-admin-page .wrs-toggle-row {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                padding: 14px 16px;
                border: 1px solid #d9e5eb;
                border-radius: 14px;
                background: #f8fbfc;
            }
            .wrs-admin-page .wrs-toggle-copy {
                display: grid;
                gap: 4px;
            }
            .wrs-admin-page .wrs-toggle-copy strong {
                font-size: 14px;
            }
            .wrs-admin-page .wrs-toggle-copy small {
                color: #5b7384;
                line-height: 1.45;
            }
            .wrs-admin-page .wrs-switch {
                position: relative;
                flex: 0 0 auto;
            }
            .wrs-admin-page .wrs-switch input {
                position: absolute;
                opacity: 0;
                pointer-events: none;
            }
            .wrs-admin-page .wrs-switch-ui {
                display: inline-block;
                width: 50px;
                height: 30px;
                border-radius: 999px;
                background: #afc0ca;
                position: relative;
                transition: background 0.2s ease;
            }
            .wrs-admin-page .wrs-switch-ui::after {
                content: "";
                position: absolute;
                top: 4px;
                left: 4px;
                width: 22px;
                height: 22px;
                border-radius: 50%;
                background: #fff;
                box-shadow: 0 2px 8px rgba(17, 43, 60, 0.18);
                transition: transform 0.2s ease;
            }
            .wrs-admin-page .wrs-switch input:checked + .wrs-switch-ui {
                background: #1f7a5c;
            }
            .wrs-admin-page .wrs-switch input:checked + .wrs-switch-ui::after {
                transform: translateX(20px);
            }
            .wrs-admin-page .wrs-module-grid {
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 12px;
            }
            .wrs-admin-page .wrs-path-list {
                display: grid;
                gap: 12px;
            }
            .wrs-admin-page .wrs-path-item {
                padding: 14px 16px;
                border-radius: 14px;
                background: #f5f9fb;
                border: 1px solid #d9e5eb;
            }
            .wrs-admin-page .wrs-path-item span {
                display: block;
                margin-bottom: 4px;
                color: #5c7384;
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 0.06em;
            }
            .wrs-admin-page .wrs-path-item code {
                word-break: break-word;
            }
            .wrs-admin-page .wrs-pair-code-box {
                margin: 14px 0 0;
                padding: 16px;
                background: #f0f7f4;
                border: 1px solid #b2d8c8;
                border-radius: 12px;
            }
            .wrs-admin-page .wrs-pair-code-box label {
                display: block;
                font-weight: 600;
                margin-bottom: 8px;
                color: #1f7a5c;
            }
            .wrs-admin-page .wrs-pair-code-value {
                display: block;
                font-family: monospace;
                font-size: 12px;
                word-break: break-all;
                padding: 10px;
                background: #fff;
                border: 1px solid #b2d8c8;
                border-radius: 8px;
                margin-bottom: 10px;
                cursor: text;
                user-select: all;
            }
            .wrs-admin-page .wrs-pair-cmd {
                display: block;
                font-family: monospace;
                font-size: 12px;
                word-break: break-all;
                padding: 8px 10px;
                background: #1e2b36;
                color: #7dd3b0;
                border-radius: 8px;
            }
            .wrs-admin-page .wrs-submit {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 16px;
                margin: 0;
            }
            .wrs-admin-page .wrs-submit small {
                color: #5b7384;
            }
            @media (max-width: 960px) {
                .wrs-admin-page .wrs-hero,
                .wrs-admin-page .wrs-grid,
                .wrs-admin-page .wrs-field-grid,
                .wrs-admin-page .wrs-module-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        <?php if (!empty($_GET['wrs-updated'])) : ?>
            <div class="notice notice-success is-dismissible"><p>WP Remote Shell settings saved.</p></div>
        <?php endif; ?>
        <?php if (!empty($_GET['wrs-pair-ready'])) : ?>
            <div class="notice notice-success is-dismissible"><p>Pairing code generated. Copy it from the <strong>CLI Pairing Code</strong> card below and paste it into the CLI. It expires in 30 minutes and works only once.</p></div>
        <?php endif; ?>
        <?php if (is_wp_error($save_error)) : ?>
            <div class="notice notice-error"><p><?php echo esc_html($save_error->get_error_message()); ?></p></div>
        <?php endif; ?>
        <?php if (is_wp_error($config)) : ?>
            <h1>WP Remote Shell</h1>
            <div class="notice notice-error"><p><?php echo esc_html($config->get_error_message()); ?></p></div>
            <p><strong>Config path:</strong> <?php echo esc_html(wrs_get_config_path()); ?></p>
            <p><strong>Storage dir:</strong> <?php echo esc_html(wrs_storage_dir()); ?></p>
            <?php return; ?>
        <?php endif; ?>
        <div class="wrs-shell">
            <section class="wrs-hero">
                <div>
                    <h1>WP Remote Shell</h1>
                    <p>Manage the plugin from WordPress instead of editing raw JSON. This screen controls transport safety, modules, telemetry, and first-run access.</p>
                </div>
                <div class="wrs-status-grid">
                    <div class="wrs-stat">
                        <span>Admin IP</span>
                        <strong><?php echo esc_html(wrs_client_ip() ?: 'Unavailable'); ?></strong>
                    </div>
                    <div class="wrs-stat">
                        <span>Token</span>
                        <strong><?php echo !empty($config['token_hash']) ? 'Configured' : 'Missing'; ?></strong>
                    </div>
                    <div class="wrs-stat">
                        <span>IP Mode</span>
                        <strong><?php echo !empty($config['allow_all_ips']) ? 'Allow All' : 'Restricted'; ?></strong>
                    </div>
                    <div class="wrs-stat">
                        <span>Master Switch</span>
                        <strong><?php echo !empty($config['modules']['master_enabled']) ? 'Enabled' : 'Disabled'; ?></strong>
                    </div>
                </div>
            </section>

            <form method="post">
                <?php wp_nonce_field('wrs_save_settings'); ?>
                <div class="wrs-grid">
                    <section class="wrs-card">
                        <h2>Setup Checklist</h2>
                        <p>This should guide a first-time user without reading raw config.</p>
                        <div class="wrs-checklist">
                            <?php foreach (wrs_admin_checklist_items($config) as $item) : ?>
                                <div class="wrs-check-item <?php echo $item['done'] ? 'is-done' : ''; ?>">
                                    <span class="wrs-check-mark"><?php echo $item['done'] ? 'OK' : '!'; ?></span>
                                    <div class="wrs-check-copy">
                                        <strong><?php echo esc_html($item['label']); ?></strong>
                                        <small><?php echo esc_html($item['detail']); ?></small>
                                    </div>
                                </div>
                            <?php endforeach; ?>
                        </div>
                    </section>

                    <?php
                    $pair_code = wrs_get_current_pair_code();
                    ?>
                    <section class="wrs-card">
                        <h2>CLI Pairing Code</h2>
                        <p>Lost access from your CLI machine? Generate a one-time code here, copy it, and paste it into the CLI. The code expires in <strong>30 minutes</strong> and works only once — generating a new code replaces any previous one.</p>
                        <?php if ($pair_code) : ?>
                            <div class="wrs-pair-code-box">
                                <label>Pairing code (click to select all, then copy):</label>
                                <code class="wrs-pair-code-value" id="wrs-pair-code-value"><?php echo esc_html($pair_code); ?></code>
                                <span class="wrs-pair-cmd">python cli/wrs.py pair <?php echo esc_html($pair_code); ?></span>
                            </div>
                            <p style="margin-top:10px;color:#1f7a5c;"><strong>&#10003; Active</strong> — paste the command above into your terminal.</p>
                        <?php else : ?>
                            <p style="color:#5b7384;margin:0 0 14px;">No active pairing code. Click the button to generate one.</p>
                        <?php endif; ?>
                        <form method="post" style="margin-top:<?php echo $pair_code ? '0' : '0'; ?>">
                            <?php wp_nonce_field('wrs_gen_pair'); ?>
                            <button type="submit" name="wrs_generate_pair" value="1" class="button button-primary">
                                <?php echo $pair_code ? 'Regenerate Pairing Code' : 'Generate CLI Pairing Code'; ?>
                            </button>
                        </form>
                    </section>

                    <section class="wrs-card">
                        <h2>Connection</h2>
                        <p>Basic site identity and runtime modes.</p>
                        <div class="wrs-field-grid">
                            <div class="wrs-field">
                                <label for="site_name">Site Name</label>
                                <input type="text" id="site_name" name="site_name" value="<?php echo esc_attr($config['site_name']); ?>" />
                            </div>
                            <div class="wrs-field">
                                <label for="site_url">Site URL</label>
                                <input type="url" id="site_url" name="site_url" value="<?php echo esc_attr($config['site_url']); ?>" />
                            </div>
                            <div class="wrs-field">
                                <label for="page_mode">Page Mode</label>
                                <select id="page_mode" name="page_mode">
                                    <option value="html" <?php selected($config['page_mode'], 'html'); ?>>HTML</option>
                                    <option value="elementor" <?php selected($config['page_mode'], 'elementor'); ?>>Elementor</option>
                                </select>
                            </div>
                            <div class="wrs-field">
                                <label for="css_mode">CSS Mode</label>
                                <select id="css_mode" name="css_mode">
                                    <option value="inline" <?php selected($config['css_mode'], 'inline'); ?>>Inline</option>
                                    <option value="enqueue" <?php selected($config['css_mode'], 'enqueue'); ?>>Enqueue</option>
                                </select>
                            </div>
                        </div>
                    </section>

                    <section class="wrs-card">
                        <h2>Access Control</h2>
                        <p>Keep setup easy first, then lock the site down to known IPs.</p>
                        <div class="wrs-toggle-list">
                            <?php wrs_render_toggle_row('allow_all_ips', 'Allow all IPs during setup', !empty($config['allow_all_ips']), 'Recommended for first-time setup. Token and signature checks still apply.'); ?>
                            <?php wrs_render_toggle_row('require_https', 'Require HTTPS', !empty($config['require_https']), 'Reject API requests unless the site is running on HTTPS.'); ?>
                            <?php wrs_render_toggle_row('module_master_enabled', 'Master enable switch', !empty($config['modules']['master_enabled']), 'Turns the plugin API on or off without uninstalling it.'); ?>
                        </div>
                        <div class="wrs-field wrs-field-full" style="margin-top:14px;">
                            <label for="allowed_ips">Allowed IPs</label>
                            <textarea id="allowed_ips" name="allowed_ips"><?php echo esc_textarea(implode("\n", $config['allowed_ips'])); ?></textarea>
                            <small>Enter one IP per line or comma separated. These are enforced when "Allow all IPs during setup" is turned off.</small>
                        </div>
                        <div class="wrs-action-row">
                            <button type="submit" name="wrs_access_preset" value="allow_all" class="button">Allow All During Setup</button>
                            <button type="submit" name="wrs_access_preset" value="current_ip" class="button">Lock To My Current IP</button>
                            <button type="submit" name="wrs_access_preset" value="append_current_ip" class="button">Add My Current IP</button>
                        </div>
                    </section>

                    <section class="wrs-card">
                        <h2>Runtime Limits</h2>
                        <p>Bounds for API safety and resource usage.</p>
                        <div class="wrs-field-grid">
                            <div class="wrs-field">
                                <label for="replay_window_seconds">Replay Window Seconds</label>
                                <input type="number" id="replay_window_seconds" name="replay_window_seconds" value="<?php echo esc_attr((string) $config['replay_window_seconds']); ?>" min="5" max="3600" />
                            </div>
                            <div class="wrs-field">
                                <label for="rate_limit_per_minute">Rate Limit Per Minute</label>
                                <input type="number" id="rate_limit_per_minute" name="rate_limit_per_minute" value="<?php echo esc_attr((string) $config['rate_limit_per_minute']); ?>" min="1" max="10000" />
                            </div>
                            <div class="wrs-field">
                                <label for="exec_timeout_seconds">Exec Timeout Seconds</label>
                                <input type="number" id="exec_timeout_seconds" name="exec_timeout_seconds" value="<?php echo esc_attr((string) $config['exec_timeout_seconds']); ?>" min="1" max="600" />
                            </div>
                            <div class="wrs-field">
                                <label for="max_output_bytes">Max Output Bytes</label>
                                <input type="number" id="max_output_bytes" name="max_output_bytes" value="<?php echo esc_attr((string) $config['max_output_bytes']); ?>" min="1024" max="10485760" />
                            </div>
                            <div class="wrs-field">
                                <label for="log_retention_count">Log Retention Count</label>
                                <input type="number" id="log_retention_count" name="log_retention_count" value="<?php echo esc_attr((string) $config['log_retention_count']); ?>" min="10" max="50000" />
                            </div>
                        </div>
                    </section>

                    <section class="wrs-card">
                        <h2>Safety And Telemetry</h2>
                        <p>Operational features that help inspection and recovery.</p>
                        <div class="wrs-toggle-list">
                            <?php wrs_render_toggle_row('checkpoint_enabled', 'Checkpoints', !empty($config['checkpoint']['enabled']), 'Create rollback points before write operations.'); ?>
                            <?php wrs_render_toggle_row('journal_enabled', 'Journal', !empty($config['journal']['enabled']), 'Keep an operation history for investigation and recovery.'); ?>
                            <?php wrs_render_toggle_row('telemetry_capture_php_errors', 'Capture PHP Errors', !empty($config['telemetry']['capture_php_errors']), 'Attach runtime PHP errors to telemetry responses.'); ?>
                            <?php wrs_render_toggle_row('telemetry_capture_memory', 'Capture Memory Usage', !empty($config['telemetry']['capture_memory']), 'Record memory metrics in server diagnostics.'); ?>
                        </div>
                    </section>

                    <section class="wrs-card wrs-card-full">
                        <h2>Modules</h2>
                        <p>Feature toggles exposed by the server config. Some modules are still partial in this repository.</p>
                        <div class="wrs-module-grid">
                            <?php foreach (wrs_admin_module_labels() as $module_key => $module_label) : ?>
                                <?php wrs_render_toggle_row('module_' . $module_key, $module_label, !empty($config['modules'][$module_key]), 'Enable or disable this module.'); ?>
                            <?php endforeach; ?>
                        </div>
                    </section>

                    <section class="wrs-card wrs-card-full">
                        <h2>Paths</h2>
                        <p>Read-only server paths used by this plugin install.</p>
                        <div class="wrs-path-list">
                            <div class="wrs-path-item">
                                <span>Config Path</span>
                                <code><?php echo esc_html(wrs_get_config_path()); ?></code>
                            </div>
                            <div class="wrs-path-item">
                                <span>Storage Directory</span>
                                <code><?php echo esc_html(wrs_storage_dir()); ?></code>
                            </div>
                        </div>
                    </section>
                </div>
                <p class="wrs-submit">
                    <small>Save here to update the live plugin config file on the server.</small>
                    <button type="submit" name="wrs_settings_submit" value="1" class="button button-primary button-large">Save Settings</button>
                </p>
            </form>
        </div>
    </div>
    <?php
}
