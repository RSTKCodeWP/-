<?php

class GlobalOptions extends CustPostType {
	public static $all_fields = array(
	);

	public static $plural_name    = "GlobalOptions"; //Plural Name for wp-admin
	public static $singular_name  = "GlobalOption"; //Singular Name for wp-admin
	public static $icon_name      = "dashicons-welcome-widgets-menus"; //the dashicons Icon to use in wordpress 4+
	public static $post_type_name = "global_options"; //the actual post type
	public static $metabox_name   = "Global Options Info"; //the name of the meta box
	public static $metabox_id     = "global_options_info"; //the actual ID of the metabox
	public static $has_archive	  = false;
	public static $supports       = array('title', ); //the default fields it suppports
	public static $api_actions	  = array(	); //Currently has no API

}

//use this area to add methods to the class


add_action( 'init', function(){ GlobalOptions::init(); });
add_action( 'add_meta_boxes', function() { return GlobalOptions::add_post_meta_box(); });
add_action( 'save_post',      function($pid) { return GlobalOptions::save_cust_post_action($pid); });

