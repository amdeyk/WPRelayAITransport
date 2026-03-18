<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_checkpoint_dir() {
    return wrs_storage_dir() . 'checkpoints/';
}

function wrs_checkpoint_path($checkpoint_id) {
    return wrs_checkpoint_dir() . $checkpoint_id . '.json';
}

function wrs_find_page_by_slug($slug) {
    $pages = get_posts(array(
        'name' => sanitize_title($slug),
        'post_type' => 'page',
        'post_status' => array('publish', 'draft', 'pending', 'private', 'future', 'trash'),
        'numberposts' => 1,
    ));
    return $pages ? $pages[0] : null;
}

function wrs_page_snapshot($post) {
    if (!$post) {
        return null;
    }

    return array(
        'id' => $post->ID,
        'slug' => $post->post_name,
        'title' => $post->post_title,
        'status' => $post->post_status,
        'html' => (string) get_post_meta($post->ID, '_wrs_source_html', true),
        'css' => (string) get_post_meta($post->ID, '_wrs_css', true),
        'canvas' => (bool) get_post_meta($post->ID, '_wrs_canvas', true),
    );
}

function wrs_create_checkpoint($op_id, $op_type, $targets) {
    $checkpoint_id = uniqid('wrs_ck_', true);
    $data = array(
        'checkpoint_id' => $checkpoint_id,
        'op_id' => $op_id,
        'op_type' => $op_type,
        'targets' => $targets,
        'created_at' => gmdate('c'),
        'snapshot' => null,
    );

    if (($targets['kind'] ?? '') === 'page' && !empty($targets['slug'])) {
        $post = wrs_find_page_by_slug($targets['slug']);
        $data['snapshot'] = wrs_page_snapshot($post);
    }

    file_put_contents(
        wrs_checkpoint_path($checkpoint_id),
        wp_json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . PHP_EOL,
        LOCK_EX
    );

    wrs_append_journal(array(
        'event' => 'CHECKPOINT_CREATED',
        'checkpoint_id' => $checkpoint_id,
        'op_id' => $op_id,
        'created_at' => gmdate('c'),
    ));

    return $data;
}


function wrs_read_checkpoint($checkpoint_id) {
    $path = wrs_checkpoint_path($checkpoint_id);
    if (!file_exists($path)) {
        return null;
    }
    return json_decode(file_get_contents($path), true);
}


function wrs_list_checkpoints($limit = 25) {
    $paths = glob(wrs_checkpoint_dir() . '*.json');
    rsort($paths);
    $items = array();
    foreach (array_slice($paths, 0, $limit) as $path) {
        $items[] = json_decode(file_get_contents($path), true);
    }
    return $items;
}


function wrs_restore_checkpoint($checkpoint_id, $dry_run = false) {
    $checkpoint = wrs_read_checkpoint($checkpoint_id);
    if (!$checkpoint) {
        return new WP_Error('wrs_checkpoint_missing', 'Checkpoint not found.', array('status' => 404));
    }

    $snapshot = $checkpoint['snapshot'] ?? null;
    $targets = $checkpoint['targets'] ?? array();
    if (($targets['kind'] ?? '') !== 'page') {
        return new WP_Error('wrs_checkpoint_unsupported', 'Only page rollback is currently supported.', array('status' => 400));
    }

    $slug = $targets['slug'] ?? '';
    $existing = wrs_find_page_by_slug($slug);
    if ($dry_run) {
        return array(
            'checkpoint_id' => $checkpoint_id,
            'dry_run' => true,
            'target_slug' => $slug,
            'action' => $snapshot ? 'restore_page' : 'trash_current_page',
        );
    }

    if ($snapshot) {
        $post_id = $existing ? $existing->ID : 0;
        $postarr = array(
            'post_title' => $snapshot['title'],
            'post_name' => $snapshot['slug'],
            'post_type' => 'page',
            'post_status' => $snapshot['status'],
            'post_content' => wrs_render_page_content($snapshot['html'], $snapshot['css'], get_post_meta($snapshot['id'], '_wrs_css_mode', true) ?: 'inline'),
        );
        if ($post_id) {
            $postarr['ID'] = $post_id;
            wp_update_post($postarr);
        } else {
            $post_id = wp_insert_post($postarr);
        }
        update_post_meta($post_id, '_wrs_source_html', $snapshot['html']);
        update_post_meta($post_id, '_wrs_css', $snapshot['css']);
        update_post_meta($post_id, '_wrs_canvas', $snapshot['canvas'] ? 1 : 0);
        $page = get_post($post_id);
        return array('checkpoint_id' => $checkpoint_id, 'page' => wrs_page_response($page));
    }

    if ($existing) {
        wp_trash_post($existing->ID);
    }
    return array('checkpoint_id' => $checkpoint_id, 'page' => array('slug' => $slug, 'deleted' => true));
}
