<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_render_page_content($html, $css, $css_mode) {
    return $html;
}

function wrs_page_css_dir() {
    $uploads = wp_get_upload_dir();
    $dir = trailingslashit($uploads['basedir']) . 'wrs/page-css/';
    wp_mkdir_p($dir);
    return $dir;
}

function wrs_page_css_url() {
    $uploads = wp_get_upload_dir();
    return trailingslashit($uploads['baseurl']) . 'wrs/page-css/';
}

function wrs_write_page_css_asset($slug, $css) {
    $slug = sanitize_title($slug);
    $path = wrs_page_css_dir() . $slug . '.css';
    file_put_contents($path, $css, LOCK_EX);
    return array(
        'path' => $path,
        'url' => wrs_page_css_url() . $slug . '.css',
    );
}

function wrs_page_error($message, $status, $retryable = false) {
    return new WP_REST_Response(array(
        'success' => false,
        'status' => 'FAILED',
        'message' => $message,
        'telemetry' => wrs_build_telemetry(array('recovery_hint' => wrs_recovery_hint($retryable, $message))),
    ), $status);
}

function wrs_page_response($post) {
    return array(
        'id' => $post->ID,
        'slug' => $post->post_name,
        'title' => $post->post_title,
        'status' => $post->post_status,
        'mode' => get_post_meta($post->ID, '_wrs_page_mode', true) ?: 'html',
        'modified' => $post->post_modified_gmt,
        'html' => (string) get_post_meta($post->ID, '_wrs_source_html', true),
        'css' => (string) get_post_meta($post->ID, '_wrs_css', true),
        'canvas' => (bool) get_post_meta($post->ID, '_wrs_canvas', true),
        'featured_image_id' => (int) get_post_thumbnail_id($post->ID),
        'seo_title' => (string) get_post_meta($post->ID, '_yoast_wpseo_title', true),
        'seo_description' => (string) get_post_meta($post->ID, '_yoast_wpseo_metadesc', true),
    );
}

// ── Elementor helpers ─────────────────────────────────────────────────────────

function wrs_is_elementor_page($post_id) {
    return get_post_meta($post_id, '_elementor_edit_mode', true) === 'builder';
}

// ── Full page inspection (works for any page, managed or not) ─────────────────

function wrs_page_inspect_data($post) {
    $post_id      = $post->ID;
    $is_front     = ((int) get_option('page_on_front') === $post_id);
    $is_managed   = (bool) get_post_meta($post_id, '_wrs_managed', true);
    $is_elementor = wrs_is_elementor_page($post_id);
    $wrs_html     = (string) get_post_meta($post_id, '_wrs_source_html', true);
    $wrs_css      = (string) get_post_meta($post_id, '_wrs_css', true);

    return array(
        'id'                   => $post_id,
        'slug'                 => $post->post_name,
        'title'                => $post->post_title,
        'status'               => $post->post_status,
        'mode'                 => get_post_meta($post_id, '_wrs_page_mode', true) ?: 'html',
        'modified'             => $post->post_modified_gmt,
        'is_front_page'        => $is_front,
        'front_page_url'       => $is_front ? home_url('/') : null,
        'is_wrs_managed'       => $is_managed,
        'builder'              => $is_elementor ? 'elementor' : 'none',
        'wrs_html_len'         => strlen($wrs_html),
        'wrs_css_len'          => strlen($wrs_css),
        'has_wrs_source'       => strlen($wrs_html) > 0,
        'has_wrs_css_override' => strlen($wrs_css) > 0,
        'has_elementor_data'   => $is_elementor ? (bool) get_post_meta($post_id, '_elementor_data', true) : false,
        'post_content_len'     => strlen($post->post_content),
        'page_url'             => get_permalink($post_id),
    );
}


function wrs_apply_page_assets($post_id, $slug, $css, $css_mode) {
    $wrote_files = array();
    update_post_meta($post_id, '_wrs_css', $css);
    update_post_meta($post_id, '_wrs_css_mode', $css_mode);

    if ($css && $css_mode === 'enqueue') {
        $asset = wrs_write_page_css_asset($slug, $css);
        update_post_meta($post_id, '_wrs_css_file', $asset['path']);
        update_post_meta($post_id, '_wrs_css_url', $asset['url']);
        $wrote_files[] = $asset['path'];
    } else {
        delete_post_meta($post_id, '_wrs_css_file');
        delete_post_meta($post_id, '_wrs_css_url');
    }

    return $wrote_files;
}

function wrs_content_apply_page(WP_REST_Request $request) {
    $started_at = microtime(true);
    $params = $request->get_json_params();
    $slug = sanitize_title($params['slug'] ?? '');
    $title = sanitize_text_field($params['title'] ?? '');
    $html = (string) ($params['html'] ?? '');
    $css = (string) ($params['css'] ?? '');
    $status = sanitize_key($params['status'] ?? 'draft');
    $canvas = !empty($params['canvas']);
    $page_mode = sanitize_key($params['page_mode'] ?? 'html');
    $css_mode = sanitize_key($params['css_mode'] ?? 'inline');

    if (!$slug || !$title) {
        return wrs_page_error('Slug and title are required.', 400, false);
    }

    $existing = wrs_find_page_by_slug($slug);
    $postarr = array(
        'post_title' => $title,
        'post_name' => $slug,
        'post_type' => 'page',
        'post_status' => $status,
        'post_content' => wrs_render_page_content($html, $css, $css_mode),
    );

    if ($existing) {
        $postarr['ID'] = $existing->ID;
        $post_id = wp_update_post($postarr, true);
    } else {
        $post_id = wp_insert_post($postarr, true);
    }

    if (is_wp_error($post_id)) {
        return wrs_page_error($post_id->get_error_message(), 500, false);
    }

    update_post_meta($post_id, '_wrs_managed', 1);
    update_post_meta($post_id, '_wrs_page_mode', $page_mode);
    update_post_meta($post_id, '_wrs_source_html', $html);
    update_post_meta($post_id, '_wrs_canvas', $canvas ? 1 : 0);
    $wrote_files = wrs_apply_page_assets($post_id, $slug, $css, $css_mode);

    $post = get_post($post_id);
    $response = array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => wrs_page_response($post),
        'telemetry' => wrs_build_telemetry(array(
            'db_rows_affected' => 1,
            'content_echo' => substr($html, 0, 120),
            'post_status_after' => $post->post_status,
            'wrote_files' => $wrote_files,
            'recovery_hint' => wrs_recovery_hint(false, 'Page synced successfully.'),
            'php_execution_ms' => (int) round((microtime(true) - $started_at) * 1000),
        )),
    );

    wrs_append_journal(array(
        'event' => 'PAGE_APPLY',
        'op_id' => $params['op_id'] ?? '',
        'page_id' => $post_id,
        'slug' => $slug,
        'status' => 'SUCCESS',
        'timestamp' => gmdate('c'),
    ));

    return rest_ensure_response($response);
}

function wrs_content_get_page(WP_REST_Request $request) {
    $slug = sanitize_title($request->get_param('slug'));
    $post = wrs_find_page_by_slug($slug);
    if (!$post) {
        return wrs_page_error('Page not found.', 404, false);
    }

    return rest_ensure_response(array(
        'success' => true,
        'page' => wrs_page_response($post),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_content_list_pages(WP_REST_Request $request = null) {
    $all  = $request && filter_var($request->get_param('all'), FILTER_VALIDATE_BOOLEAN);
    $args = array(
        'post_type'      => 'page',
        'posts_per_page' => 200,
        'post_status'    => array('publish', 'draft', 'pending', 'private', 'future'),
        'orderby'        => 'modified',
        'order'          => 'DESC',
    );
    if (!$all) {
        $args['meta_key'] = '_wrs_managed';
    }
    $posts = get_posts($args);
    $pages = array_map($all ? 'wrs_page_inspect_data' : 'wrs_page_response', $posts);
    return rest_ensure_response(array(
        'success' => true,
        'pages' => array_values($pages),
        'telemetry' => wrs_build_telemetry(),
    ));
}

function wrs_content_publish_page(WP_REST_Request $request) {
    $started_at = microtime(true);
    $slug = sanitize_title($request->get_json_params()['slug'] ?? '');
    $post = wrs_find_page_by_slug($slug);
    if (!$post) {
        return wrs_page_error('Page not found.', 404, false);
    }

    wp_update_post(array('ID' => $post->ID, 'post_status' => 'publish'));
    return rest_ensure_response(array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => wrs_page_response(get_post($post->ID)),
        'telemetry' => wrs_build_telemetry(array(
            'db_rows_affected' => 1,
            'post_status_after' => 'publish',
            'recovery_hint' => wrs_recovery_hint(false, 'Page published successfully.'),
            'php_execution_ms' => (int) round((microtime(true) - $started_at) * 1000),
        )),
    ));
}

function wrs_content_delete_page(WP_REST_Request $request) {
    $started_at = microtime(true);
    $slug = sanitize_title($request->get_json_params()['slug'] ?? '');
    $post = wrs_find_page_by_slug($slug);
    if (!$post) {
        return wrs_page_error('Page not found.', 404, false);
    }

    wp_trash_post($post->ID);
    return rest_ensure_response(array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => array('id' => $post->ID, 'slug' => $slug),
        'telemetry' => wrs_build_telemetry(array(
            'db_rows_affected' => 1,
            'post_status_after' => 'trash',
            'recovery_hint' => wrs_recovery_hint(false, 'Page moved to trash.'),
            'php_execution_ms' => (int) round((microtime(true) - $started_at) * 1000),
        )),
    ));
}


function wrs_content_update_css(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $slug = sanitize_title($params['slug'] ?? '');
    $css = (string) ($params['css'] ?? '');
    $post = wrs_find_page_by_slug($slug);
    if (!$post) {
        return wrs_page_error('Page not found.', 404, false);
    }
    $css_mode = sanitize_key($params['css_mode'] ?? get_post_meta($post->ID, '_wrs_css_mode', true) ?: 'inline');
    $wrote_files = wrs_apply_page_assets($post->ID, $slug, $css, $css_mode);
    return rest_ensure_response(array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => wrs_page_response(get_post($post->ID)),
        'telemetry' => wrs_build_telemetry(array(
            'db_rows_affected' => 1,
            'wrote_files' => $wrote_files,
            'recovery_hint' => wrs_recovery_hint(false, 'CSS updated successfully.'),
        )),
    ));
}


function wrs_content_clone_page(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $slug = sanitize_title($params['slug'] ?? '');
    $new_slug = sanitize_title($params['new_slug'] ?? '');
    $new_title = sanitize_text_field($params['new_title'] ?? '');
    $post = wrs_find_page_by_slug($slug);
    if (!$post || !$new_slug) {
        return wrs_page_error('Source page and new slug are required.', 400, false);
    }
    $source = wrs_page_response($post);
    $clone_id = wp_insert_post(array(
        'post_title' => $new_title ?: ($source['title'] . ' Copy'),
        'post_name' => $new_slug,
        'post_type' => 'page',
        'post_status' => 'draft',
        'post_content' => $source['html'],
    ));
    update_post_meta($clone_id, '_wrs_managed', 1);
    update_post_meta($clone_id, '_wrs_page_mode', $source['mode']);
    update_post_meta($clone_id, '_wrs_source_html', $source['html']);
    update_post_meta($clone_id, '_wrs_canvas', $source['canvas'] ? 1 : 0);
    wrs_apply_page_assets($clone_id, $new_slug, $source['css'], get_post_meta($post->ID, '_wrs_css_mode', true) ?: 'inline');
    return rest_ensure_response(array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => wrs_page_response(get_post($clone_id)),
        'telemetry' => wrs_build_telemetry(array('db_rows_affected' => 1)),
    ));
}


function wrs_content_set_image(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $slug = sanitize_title($params['slug'] ?? '');
    $media_id = (int) ($params['media_id'] ?? 0);
    $post = wrs_find_page_by_slug($slug);
    if (!$post || !$media_id) {
        return wrs_page_error('Page and media_id are required.', 400, false);
    }
    set_post_thumbnail($post->ID, $media_id);
    return rest_ensure_response(array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => wrs_page_response(get_post($post->ID)),
        'telemetry' => wrs_build_telemetry(array('db_rows_affected' => 1)),
    ));
}


function wrs_content_set_meta(WP_REST_Request $request) {
    $params = $request->get_json_params();
    $slug = sanitize_title($params['slug'] ?? '');
    $title = sanitize_text_field($params['title'] ?? '');
    $description = sanitize_textarea_field($params['description'] ?? '');
    $post = wrs_find_page_by_slug($slug);
    if (!$post) {
        return wrs_page_error('Page not found.', 404, false);
    }
    update_post_meta($post->ID, '_yoast_wpseo_title', $title);
    update_post_meta($post->ID, '_yoast_wpseo_metadesc', $description);
    update_post_meta($post->ID, 'rank_math_title', $title);
    update_post_meta($post->ID, 'rank_math_description', $description);
    return rest_ensure_response(array(
        'success' => true,
        'status' => 'SUCCESS',
        'page' => wrs_page_response(get_post($post->ID)),
        'telemetry' => wrs_build_telemetry(array('db_rows_affected' => 1)),
    ));
}

// ── Page inspection ───────────────────────────────────────────────────────────
// Resolves any page by slug, id, or front=1. Does not require _wrs_managed.

function wrs_content_inspect_page(WP_REST_Request $request) {
    $slug    = sanitize_title($request->get_param('slug') ?: '');
    $page_id = (int) $request->get_param('id');
    $front   = filter_var($request->get_param('front'), FILTER_VALIDATE_BOOLEAN);

    if ($front) {
        $page_id = (int) get_option('page_on_front');
    }

    if ($page_id) {
        $post = get_post($page_id);
    } elseif ($slug) {
        $post = wrs_find_page_by_slug($slug);
    } else {
        return wrs_page_error('Provide slug, id, or front=1.', 400, false);
    }

    if (!$post || $post->post_type !== 'page') {
        return wrs_page_error('Page not found.', 404, false);
    }

    return rest_ensure_response(array(
        'success'   => true,
        'page'      => wrs_page_inspect_data($post),
        'telemetry' => wrs_build_telemetry(),
    ));
}

// ── Page adoption ─────────────────────────────────────────────────────────────
// Marks an existing unmanaged page as WRS-managed. Must be called explicitly.
// Does NOT overwrite Elementor data. For HTML pages, snapshots current
// post_content into _wrs_source_html only if the field is currently empty.

function wrs_content_adopt_page(WP_REST_Request $request) {
    $params  = $request->get_json_params();
    $slug    = sanitize_title($params['slug'] ?? '');
    $page_id = (int) ($params['id'] ?? 0);

    if ($page_id) {
        $post = get_post($page_id);
    } elseif ($slug) {
        $post = wrs_find_page_by_slug($slug);
    } else {
        return wrs_page_error('Provide slug or id.', 400, false);
    }

    if (!$post || $post->post_type !== 'page') {
        return wrs_page_error('Page not found.', 404, false);
    }

    if (get_post_meta($post->ID, '_wrs_managed', true)) {
        return new WP_REST_Response(array(
            'success' => false,
            'status'  => 'ALREADY_MANAGED',
            'message' => 'Page is already WRS-managed. Use page apply to update content.',
            'page'    => wrs_page_inspect_data($post),
            'telemetry' => wrs_build_telemetry(),
        ), 409);
    }

    $page_mode = wrs_is_elementor_page($post->ID) ? 'elementor' : 'html';
    update_post_meta($post->ID, '_wrs_managed', 1);
    update_post_meta($post->ID, '_wrs_page_mode', $page_mode);

    // For HTML pages only: seed _wrs_source_html from post_content if absent.
    // Elementor pages: leave all builder meta untouched.
    if ($page_mode === 'html' && !get_post_meta($post->ID, '_wrs_source_html', true)) {
        update_post_meta($post->ID, '_wrs_source_html', $post->post_content);
    }

    wrs_append_journal(array(
        'event'     => 'PAGE_ADOPTED',
        'op_id'     => sanitize_text_field($params['op_id'] ?? ''),
        'page_id'   => $post->ID,
        'slug'      => $post->post_name,
        'page_mode' => $page_mode,
        'timestamp' => gmdate('c'),
    ));

    return rest_ensure_response(array(
        'success'   => true,
        'status'    => 'SUCCESS',
        'page'      => wrs_page_inspect_data(get_post($post->ID)),
        'telemetry' => wrs_build_telemetry(array('db_rows_affected' => 1)),
    ));
}

// ── Elementor: get ────────────────────────────────────────────────────────────
// Returns the raw Elementor JSON data for a page. Read-only. Safe on live pages.

function wrs_content_elementor_get(WP_REST_Request $request) {
    $slug    = sanitize_title($request->get_param('slug') ?: '');
    $page_id = (int) $request->get_param('id');

    if ($page_id) {
        $post = get_post($page_id);
    } elseif ($slug) {
        $post = wrs_find_page_by_slug($slug);
    } else {
        return wrs_page_error('Provide slug or id.', 400, false);
    }

    if (!$post || $post->post_type !== 'page') {
        return wrs_page_error('Page not found.', 404, false);
    }

    if (!wrs_is_elementor_page($post->ID)) {
        return wrs_page_error('Page is not an Elementor page.', 400, false);
    }

    $raw  = get_post_meta($post->ID, '_elementor_data', true);
    $data = is_string($raw) ? json_decode($raw, true) : ($raw ?: array());
    $page_settings = get_post_meta($post->ID, '_elementor_page_settings', true) ?: array();

    return rest_ensure_response(array(
        'success'        => true,
        'page_id'        => $post->ID,
        'slug'           => $post->post_name,
        'title'          => $post->post_title,
        'elementor_data' => $data,
        'page_settings'  => $page_settings,
        'telemetry'      => wrs_build_telemetry(),
    ));
}

// ── Elementor: set ────────────────────────────────────────────────────────────
// Writes Elementor JSON data back to a page. Clears Elementor's CSS cache so
// styles regenerate on the next page view. Does NOT touch post_content or
// _wrs_canvas, so the page stays in Elementor's rendering path.

function wrs_content_elementor_set(WP_REST_Request $request) {
    $started_at = microtime(true);
    $params     = $request->get_json_params();
    $slug       = sanitize_title($params['slug'] ?? '');
    $page_id    = (int) ($params['id'] ?? 0);

    if ($page_id) {
        $post = get_post($page_id);
    } elseif ($slug) {
        $post = wrs_find_page_by_slug($slug);
    } else {
        return wrs_page_error('Provide slug or id.', 400, false);
    }

    if (!$post || $post->post_type !== 'page') {
        return wrs_page_error('Page not found.', 404, false);
    }

    if (!wrs_is_elementor_page($post->ID)) {
        return wrs_page_error('Page is not an Elementor page. Use /content/page/apply for HTML pages.', 400, false);
    }

    $elementor_data = $params['elementor_data'] ?? null;
    if ($elementor_data === null) {
        return wrs_page_error('elementor_data is required.', 400, false);
    }

    // Elementor stores _elementor_data as a JSON string with slashes escaped.
    $json = is_string($elementor_data)
        ? $elementor_data
        : wp_json_encode($elementor_data, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    update_post_meta($post->ID, '_elementor_data', wp_slash($json));

    if (isset($params['page_settings']) && is_array($params['page_settings'])) {
        update_post_meta($post->ID, '_elementor_page_settings', $params['page_settings']);
    }

    // Clear Elementor's generated CSS so it regenerates on the next page view.
    delete_post_meta($post->ID, '_elementor_css');

    // Bump post_modified so caches and CDNs know the page changed.
    wp_update_post(array(
        'ID'                => $post->ID,
        'post_modified'     => current_time('mysql'),
        'post_modified_gmt' => current_time('mysql', true),
    ));

    wrs_append_journal(array(
        'event'     => 'ELEMENTOR_DATA_APPLY',
        'op_id'     => sanitize_text_field($params['op_id'] ?? ''),
        'page_id'   => $post->ID,
        'slug'      => $post->post_name,
        'status'    => 'SUCCESS',
        'timestamp' => gmdate('c'),
    ));

    return rest_ensure_response(array(
        'success'   => true,
        'status'    => 'SUCCESS',
        'page_id'   => $post->ID,
        'slug'      => $post->post_name,
        'telemetry' => wrs_build_telemetry(array(
            'db_rows_affected' => 1,
            'php_execution_ms' => (int) round((microtime(true) - $started_at) * 1000),
        )),
    ));
}
