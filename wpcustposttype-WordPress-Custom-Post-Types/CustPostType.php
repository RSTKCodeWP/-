<?php

/*
    author: @paulnurkkala
    description: make adding custom post types and interacting with them not painful
*/

class CustPostType{
	//quick declaration of all fields that need to be filled out
	public static $all_fields,
	              $plural_name,
	              $singular_name,
	              $icon_name,
	              $post_type_name,
	              $supports,
	              $metabox_name,
	              $metabox_id,
	              $api_actions,
	              $extra_args;

	//initializes the funciton, defining the custom post type
	public static function init(){
		//define the labels for the custom post type
		$labels = array(
			'name'               => _x(static::$plural_name,               static::$plural_name . 'general name'),
			'singular_name '     => _x(static::$singular_name,             static::$singular_name . ' singular name'),
			'add_new'            => _x('Create ' . static::$singular_name, static::$singular_name),
			'add_new_item'       => __('Create ' . static::$singular_name),
			'edit_item'          => __('Edit ' . static::$singular_name),
			'new_item'           => __('New ' .  static::$singular_name),
			'all_items'          => __('All ' .  static::$plural_name),
			'view_item'          => __('View ' . static::$singular_name),
			'search_items'       => __('Search ' . static::$plural_name),
			'not_found'          => __('No '. static::$plural_name.' found'),
			'not_found_in_trash' => __('No '.static::$plural_name.' found in the Trash'),
			'parent_item_colon'  => '',
			'menu_name'          => static::$plural_name, 
		);


		//define the arguments that will go into register
		$args = array(
			'labels'        => $labels,
			'description'   => static::$plural_name,
			'public'        => true,
			'supports'      => static::$supports,
			'has_archive'   => true,
			'menu_icon'     => static::$icon_name,
		);
		//set hierarchy status if true
		if(isset(static::$hierarchical)){
			if(static::$hierarchical){
				$args['hierarchical'] = true;
			}
			else{
			}
		}

		//extra args that need to be attached when the custom post type is registered
		//only called if the extra args setting is included
		if( isset(static::$extra_args)){
			// Get all extra args, and attach them to the args.
			foreach (static::$extra_args as $key => $value) {
				$args[$key] = $value;
			}
		}

		//register the post type
		register_post_type(static::$post_type_name, $args);

		//hook into init api actions method
		static::init_api_actions();
	}

	//adds the custom post type's meta box
	public static function add_post_meta_box(){
		add_meta_box(
			static::$metabox_id,
			__( static::$metabox_name, 'myplugin_textdomain' ),
			array( 'CustPostType', 'render_meta_box_content' ),
			static::$post_type_name,
			'normal',
			'core',
			array(static::$all_fields)//because we have to declare the class as "CustPostType" and not the child class, we have to pass it a list of all fields to be printed out
		);
	}

	//prints out the metabox content
	public static function render_meta_box_content( $post, $args ){
		wp_nonce_field( plugin_basename( __FILE__ ), 'content_nonce' );

		//get the list of fields that were passed in by the add_post_meta_box
		$all_fields = $args["args"][0];

		//get all meta data
		$post = static::post_get_full($post, $all_fields);

		//for each of the metabox fields, print them out
		echo '<style>.cust-post-div{max-width: 100%;}.cust-post-div input,textarea{width:100%;max-width: 600px;margin:0 0 10px}.cust-post-div input[type=checkbox]{width:inherit;display:block}.cust-post-field{padding:20px;margin:20px 0}.sg-user-selector{max-height:200px;overflow:scroll}.sg-help-text{padding:0 20px;margin:5px;font-size:12px;color:#8e8e8e}.cf:after,.cf:before{content:" ";display:table}.cf:after{clear:both}</style>';
		echo "<div class='cust-post-div'>";
		echo '<div ng-controller="SGCustPostBackend as main">';

		foreach ($all_fields as $field) {
			echo '<div class="cust-post-field">';
			static::choose_field_output(
				//using issets because of some errors that were showing up in my testing (due to turning on debugging)
				isset($field['meta'])             ? $field['meta']             : '',
				isset($field['label'])            ? $field['label']            : '',
				isset($field['placeholder'])      ? $field['placeholder']      : '',
				$post,
				isset($field['type'])             ? $field['type']             : '',
				isset($field['picker_post_type']) ? $field['picker_post_type'] : '',
				isset($field['picker_action'])    ? $field['picker_action']    : '',
				isset($field['function_name'])    ? $field['function_name']    : '',
				isset($field['help_text'])        ? $field['help_text']        : '',
				isset($field['selections'])       ? $field['selections']       : '',
				isset($field['template'])         ? $field['template']         : '',
				isset($field['controller'])       ? $field['controller']       : ''
			);
 			echo '</div>';
		}
		echo "</div>";
  		echo "</div>";
	}

	//action that's called when the post is saved
	public static function save_cust_post_action( $post_id ) {
		//if saving, hold on
		if( ! isset($_POST['post_type']))
			return;

		if( $_POST['post_type'] == static::$post_type_name){

			if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE )
				return;

  		    //if nonce is not valid, fail
			if ( !wp_verify_nonce( $_POST['content_nonce'], plugin_basename( __FILE__ ) ) )
				return;

			if ( 'page' == $_POST['post_type'] ) {
				if ( !current_user_can( 'edit_page', $post_id ) )
					return;
			} else {
				if ( !current_user_can( 'edit_post', $post_id ) )
					return;
			}

  		    //save the fields, given all fields and the $_POST data
			static::save_cust_post_fields($post_id, static::$all_fields, $_POST);

		    //custom post meta that won't be set on create that we can use to check if this is a new post or not
  		    //if this meta attribute isn't set yet, then this is a new post
			$termid = get_post_meta($post_id, '_termid', true);
			if ($termid == '') {
				if(method_exists(get_called_class(), 'post_initial_save')){
					static::post_initial_save($post_id);
				}
				$termid = 'update';
			}

			update_post_meta($post_id, '_termid', $termid);
		}
	}

    // Given $posts, a list of posts, group them according to values found in their
    // group-by filed, identified by $group_by.
    //
    // If the group-by field is array-valued, the post will end up in multiple groups, one
    // for each value in the array.
    //
    // If the group-by field is not found in the post, the post will not appear in any
    // group.
    //
    // Returns an array indexed by group-by values.
    private static function group_by($posts, $group_by) {
        $groups = array();      // Return value
        foreach ($posts as $post) {
            if (array_key_exists($group_by, $post)) {
                // Group-by field exists in this post.
                $value = $post->$group_by;
                if (!is_array($value)) {
                    // If the value of the group-by field is atomic, convert it into a
                    // singleton array.
                    $value = array($value);
                }

                // Store the post in the appropriate group-by array. Create the array if
                // necessary.
                foreach ($value as $val) {
                    if (!array_key_exists($val, $groups)) {
                        $groups[$val] = array();
                    }
                    array_push($groups[$val], $post);
                }
            }
        }

        return $groups;
    }

    /*
      author: @BoringCode
      description: Internal API to get a list of taxonomies and their posts
    */
   public static function list_taxonomy($taxonomy) {
   	$terms = get_terms($taxonomy);
   	$tax_array = array();
   	foreach($terms as $term) {
   		$post_args = array(
   			'tax_query' => array(
   				array(
   					'taxonomy' => $taxonomy,
   					'terms'    => $term->term_id,
   				),
   			),
   			'post_type' => self::$post_type_name,
   			'posts_per_page' => -1
   		);
   		$tax_array[] = array(
   			"name" => $term->name,
				"data" => $term,
				"permalink" => get_term_link($term),
				"posts" => get_posts($post_args)
   		);
   	}
   	return $tax_array;
   }

	/*
		author: @tomnurkkala
		descripiton: Retrieve a list of all posts of the current post type.
	*/
	public static function api_list($post_data) {
		$group_by = (isset($post_data['group_by']) ? $post_data['group_by'] : NULL);
		$order_by = (isset($post_data['order_by']) ? $post_data['order_by'] : "post_date");

		$args = array('nopaging'    => TRUE,
                      'order_by'    => $order_by,
                      'post_status' => 'publish',
                      'post_type'   => static::$post_type_name);

        $query = new WP_Query($args);
        $posts = $query->get_posts();

        // Apparently, the only way to pass an anonymous function is to give it a
        // name. Which isn't anonymous.
        $taxonomy_name = function($taxonomy) {
            return $taxonomy->name;
        };

        // Get complete data for each post.
		$full_posts = array();  // Post plus other data
		foreach ($posts as $post) {
            // Get all the metadata for this post.
			$full_post = static::post_get_full($post, static::$all_fields);

            // For each taxonomy associated with this post, add an attribute whose name is
            // that of the taxonomy (e.g., 'product_type' and whose value is an array of
            // values of that type (e.g., array(0 => 'Bundle', 1 => 'Product')).
            foreach (get_object_taxonomies(static::$post_type_name, 'objects') as $taxonomy) {
                $term_objects = get_the_terms($post, $taxonomy->name);
                if($term_objects){
	                $full_post->{$taxonomy->name} = array_map($taxonomy_name, $term_objects);
                }
            }

			array_push($full_posts, $full_post);
		}

        if ($group_by) {
            // Handle group_by parameter.
            $grouped_posts = static::group_by($full_posts, $group_by);
            APIResponse::init(TRUE,
                              sprintf("Grouped %d posts into %d groups by '%s'",
                                      count($full_posts), count($grouped_posts), $group_by),
                              $grouped_posts);

        } else {
            // Return everything.
            APIResponse::init(TRUE,
                              sprintf("Found %d of type '%s'", count($posts), static::$post_type_name),
                              $full_posts);
        }
	}

	/*
		author: @paulnurkkala
		descripiton: Look up some object given an ID, check for ownership permissions if required
	*/
	public static function api_retrieve($data = NULL, $require_ownership=false) {
		$thing_id = isset($data['id']) ? $data['id'] : FALSE;

		if (! $thing_id){
			APIResponse::init(FALSE, "You did not provide the ID of what you were trying to look up.", array());
		}

		$thing = get_post($thing_id);

		//if the thing was not found at all
		if((! $thing) || ( $thing->post_type != static::$post_type_name )){
			APIResponse::init(FALSE, 'Could not find the requested ' . static::$post_type_name, array());
		}

		$full_thing = static::post_get_full($thing, static::$all_fields);

		if($require_ownership){
			static::user_is_owner($full_thing->ID);
		}

		APIResponse::init(TRUE, 'Found the ' . static::$post_type_name, $full_thing);
	}

	/*
		author: @paulnurkkala
		descripiton: Look up some object given an ID, check for ownership permissions if required, and then delete the thing
	*/
	public static function api_update($data, $require_ownership=False){
		$thing_id = isset($data['id']) ? $data['id'] : FALSE;

		if (! $thing_id){
			APIResponse::init(FALSE, "You did not provide the ID of what you were trying to look up.", array());
		}

		$thing = get_post($thing_id);

		//if the thing was not found at all
		if((! $thing) || ( $thing->post_type != static::$post_type_name )){
			APIResponse::init(FALSE, 'Could not find the requested ' . static::$post_type_name, array());
		}

		//grab the whole thing, so that we have all relevant information
		$full_thing = static::post_get_full($thing, static::$all_fields);

		if($require_ownership){
			static::user_is_owner($full_thing->ID);
		}

		//these change the base wordpress things if they're set
		$post_title =   isset($data['post_title'])   ? $data['post_title']   : FALSE;
		$post_content = isset($data['post_content']) ? $data['post_content'] : FALSE;

		if($post_title){
			wp_update_post(array('ID'=>$full_thing->ID, 'post_title'=>$post_title));
		}
		if($post_content){
			wp_update_post(array('ID'=>$full_thing->ID, 'post_content'=>$post_content));
		}

		//at this point, we've checked all permissions, and we are allowed to update this thing
		//look at all available fields on the custom post type, then search through the data that was sent in and extract that information and save it

		foreach (static::get_all_fields() as $field) {
			if(isset($data[$field])){
				update_post_meta( $full_thing->ID, $field, $data[$field]);
			}
		}

		//re-grab the thing from the database to make sure that we're returning the updated information
		$full_thing = static::post_get_full(get_post($full_thing->ID), static::$all_fields);

		APIResponse::init(TRUE, 'Updated the ' . static::$post_type_name, $full_thing);
	}

	/*
		author: @paulnurkkala
		descripiton: Look up some object given an ID, check for ownership permissions if required, and then delete the thing
	*/
	public static function api_delete($data, $require_ownership=False){
		$thing_id = isset($data['id']) ? $data['id'] : FALSE;

		if (! $thing_id){
			APIResponse::init(FALSE, "You did not provide the ID of what you were trying to look up.", array());
		}

		$thing = get_post($thing_id);

		//if the thing was not found at all
		if((! $thing) || ( $thing->post_type != static::$post_type_name )){
			APIResponse::init(FALSE, 'Could not find the requested ' . static::$post_type_name, array());
		}

		//grab the whole thing, so that we have all relevant information
		$full_thing = static::post_get_full($thing, static::$all_fields);

		if($require_ownership){
			static::user_is_owner($full_thing->ID);
		}

		//at this point, we've checked all permissions, and we are allowed to delete this thing
		wp_delete_post($full_thing->ID);

		APIResponse::init(TRUE, 'Deleted the ' . static::$post_type_name, array());
	}


	/*
		author: @paulnurkkala
		description: checks to see if the user is the owner of the given thing
	*/
	public static function user_is_owner($thing_id, $user_id=None){
		$full_thing = static::post_get_full(get_post($thing_id), static::$all_fields);

		//if the programmer provided a user ID when implementing this function, then we're going to check that the given user can change the thing. If one wasn't provided, check the authenticated user.
		$user_id;
		if( ! $user_id ){
			$user_id = wp_get_current_user();
			$user_id = $user_id->ID;
		}
		$user_id         = intval($user_id);
		$current_user_id = intval(wp_get_current_user()->ID);

		$ownership_string = static::$post_type_name . '_owner';

		//if the given user is not the owner and not an admin

		$thing_owner_id = intval($full_thing->$ownership_string);

		//if the authenticated user and the owner of the thing are the same, skip everything else
		if( $thing_owner_id == $current_user_id ){
			return True;
		}

		//if the user that we are checking is NOT the authenticated user
		//and the authenticated user is NOT an administrator
		//then complain
		static::is_user_or_admin($user_id);
		return True;

	}

	public static function user_is_administrator($uid){
		return user_can($uid, "administrator");
	}


	/*
		author: @paulnurkkala
		description: use this function to save all content from the $_POST data, and then assign it to a user if you provide a user ID
	*/
	public static function initial_save($data, $user_id=None){
		//create the post
		$args = array(
			'post_title'   => $data['post_title'],
			'post_content' => $data['post_content'],
			'post_status'  => 'publish',
			'post_type'    => static::$post_type_name,
		);

		//do the actual work of saving the thing
		$new_thing = wp_insert_post($args);

		//get this post's meta fields, add the meta information that was passed from the API
		foreach (static::get_all_fields() as $field) {
			if(isset($data[$field])){
				update_post_meta( $new_thing, $field, $data[$field]);
			}
		}

		//assign this to the user
		if($user_id){
			$owner_field = static::$post_type_name . "_owner";
			update_post_meta($new_thing, $owner_field, $user_id);
		}

		$full_thing = static::post_get_full(get_post($new_thing), static::$all_fields);
		return $full_thing;

	}

	public static function post_initial_save($pid){
		error_log('post initial save Custom Post Type');
	}

	//does different htings based on each type of field -- in the case of a number, we need to convert it back to an int
	public static function save_cust_post_fields($post_id, $field_array, $post_data){
	  	//loop through custom meta fields, and save them to the post meta
		foreach ($field_array as $field) {
			$field_type   = $field['type'];
			$field_string = $field['meta'];

			switch ($field_type) {
				case 'number':
				    update_post_meta($post_id, $field_string, (int) $post_data[$field_string]);
					break;

				case 'media':
				    //update the image url field
				    update_post_meta($post_id, $field_string, $post_data[$field_string]);

				    //update the image alt field
				    update_post_meta($post_id, $field_string.'_alt', $post_data[$field_string.'_alt']);
				    break;

				default:
				    update_post_meta($post_id, $field_string, $post_data[$field_string]);
					break;
			}
		}
	}

	// Get all metabox information for the post.
	public static function post_get_full($post, $all_fields){
   	    // Too lazy to change everything else.
		$pid = $post->ID;

		$post_array = $all_fields;
		foreach ($post_array as $field) {
			$field_string = $field["meta"];
			$post->$field_string = get_post_meta($pid, $field_string, TRUE);

			if($field["type"] == 'json'){
				$post->$field_string = json_decode($post->$field_string);
			}

		}

		$post->permalink = get_permalink( $post->ID );

		return $post;
	}

	//given a field, decide what type of HTML to output, and echo out the info given each
	public static function choose_field_output($meta, $label, $placeholder, $post, $type, $picker_post_type, $picker_action, $function_name, $help_text, $selections, $template, $controller){
   		switch ($type) {
   			case 'text':
   			    static::print_input_field($meta, $label, $placeholder, $post, $help_text);
   			    break;

   			case 'textarea':
   			    static::print_textarea_field($meta, $label, $placeholder, $post, $help_text);
   			    break;

   			case 'number':
   			    static::print_number_field($meta, $label, $placeholder, $post, $help_text);
   			    break;

   			case 'checkbox':
   			    static::print_checkbox_field($meta, $label, $post, $help_text);
   			    break;

   			case 'select':
   			    static::print_select_field($meta, $label, $post, $help_text, $selections);
   			    break;

   			case 'id_picker':
   			    static::print_id_picker($meta, $label, $placeholder, $post, $picker_post_type, $picker_action, $help_text);
   			    break;

   			case 'media':
   			    static::print_media_field($meta, $label, $placeholder, $post, $help_text);
   			    break;

   			case 'related_cpt':
   				static::print_related_cpt_field($meta, $label, $placeholder, $post, $help_text);
   				break;

   			case 'gallery':
   				static::print_gallery_field($meta, $label, $placeholder, $post, $help_text);
   				break;

   			case 'json':
   				static::print_json_field($meta, $label, $post, $help_text, $template, $controller);
   				break;

   			case 'custom':
     			//static::$function_name();
   			    call_user_func_array($function_name, array($meta, $label, $placeholder, $post, $type, $picker_post_type, $picker_action, $function_name, $help_text));
   			    break;
   			default:
   			    static::print_input_field($meta, $label, $placeholder, $post, $help_text);
   			    break;
   		}
   	}

   	//prints an input[type='text']
   	public static function print_input_field($meta, $label, $placeholder, $post, $help_text){
   		echo '<label for="'. $meta. '">'.$label.'</label>';
   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}
   		echo '<input type="text" id="'.$meta.'" name="'.$meta.'" placeholder="'.$placeholder.'" value="'. $post->$meta . '"/>';
   		echo '<br/>';
   	}

   	//prints a textarea field
   	public static function print_textarea_field($meta, $label, $placeholder, $post, $help_text){
   		echo '<label for="'. $meta. '">'.$label.'</label>';
   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}
   		echo '<textarea id="'.$meta.'" name="'.$meta.'" placeholder="'.$placeholder.'" rows="5">' . $post->$meta . '</textarea>';
   		echo '<br/>';
   	}

   	//prints an input[type='number']
   	public static function print_number_field($meta, $label, $placeholder, $post, $help_text){
   		echo '<label for="'. $meta. '">'.$label.'</label>';
   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}
   		echo '<input type="number" id="'.$meta.'" name="'.$meta.'" placeholder="'.$placeholder.'" value="'. (int) $post->$meta . '"/>';
   		echo '<br/>';
   	}

   	//prints an input[type="checkbox"], for a bool
   	public static function print_checkbox_field($meta, $label, $post, $help_text){
   		echo '<label for="'.$meta.'">'.$label.'</label>';

   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}

   		if($post->$meta){
   			echo '<input type="checkbox" id="'.$meta.'" name="'.$meta.'" checked="checked"/>';
   		}
   		else{
   			echo '<input type="checkbox" id="'.$meta.'" name="'.$meta.'"/>';
   		}
   		echo '<br/>';
   	}

   	//prints an input[type='number']
   	public static function print_select_field($meta, $label, $post, $help_text, $selections){
   		echo '<label for="'. $meta. '">'.$label.'</label>';
   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}
   		echo '<select id="'.$meta.'" name="'.$meta.'" >';
   		echo '<option value="">--SELECT--</option>';
   		foreach ($selections as $s) {
   			echo '<option ' . selected($s, $post->$meta ) . ' >' . $s . '</option>';
   		}
   		echo '</select>';

   		//echo '<input type="number" id="'.$meta.'" name="'.$meta.'" placeholder="'.$placeholder.'" value="'. (int) $post->$meta . '"/>';
   		echo '<br/>';

   	}

   	//prints an input[type="checkbox"], for a bool
   	public static function print_id_picker($meta, $label, $placeholder, $post, $picker_post_type, $picker_action, $help_text){
   		echo '<label for="'.$meta.'">'.$label.'</label>';

   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}

   		echo '<style>.sghighlight{background-color:#7ad03a;}</style>';

   		//prints out the controller for the ID Picker
   		echo '<div ng-init="main.init_picker({action: \'' . $picker_action .'\', chosen: \''.$post->$meta.'\'})"</div>';


   		echo '<input type="hidden" id="'.$meta.'" name="'.$meta.'" placeholder="'.$placeholder.'" ng-model="main.chosen_thing" ng-value="main.chosen_thing" ng-init="'. $post->$meta . '"/>';


    	echo '<br/>';

    	echo '<input type="text" placeholder="Name/Email" ng-model="search.$"/>';
    	echo '<input type="text" placeholder="ID" ng-model="search.ID"/>';

    	echo "<div class='sg-user-selector'</div>";
    	    echo '<ul>';
    	        echo '<li ng-repeat="thing in things | filter:search" ng-class="{\'sghighlight\' : thing.ID == main.chosen_thing}">';
    	            echo "<a href='#' ng-click='main.chose_thing(thing)'>Choose</a> | ";
    	            echo '({{thing.ID}}) {{thing.post_title}} {{thing.display_name}}';
    	        echo '</li>';
    	    echo '</ul>';
    	echo "</div>";
    	echo "</div>";
   	}

   	public static function print_media_field($meta, $label, $placeholder, $post, $help_text){
   		//initialize this particular value

   		echo "<div class='media-field cf'>";
   		$meta_alt = $meta.'_alt';
   		echo '<div ng-init="
   		    main.datas.'.$meta.'=\''.$post->$meta.'\';
   		    main.datas.'.$meta.'_alt=\''.$post->$meta_alt.'\'
   		"></div>';

   		//set the actual input field
   		echo '<label for="'.$meta.'">'.$label.'</label>';

   		//display the chosen image, if it's set
   		echo '<p><img style="max-width:200px;" ng-show="main.datas.'.$meta.'" ng-src="{{main.datas.'.$meta.'}}"/></p>';

   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}

   		echo '<input name="'.$meta.'" id="'.$meta.'" type="text" readonly placeholder="'.$placeholder.'" ng-model="main.datas.'.$meta.'" ng-value="main.datas.'.$meta.'"/><br>';

   		//alt field
   		echo '<label for="'.$meta.'_alt">'.$label.' Alt</label> ';
   		echo '<input name="'.$meta.'_alt" id="'.$meta.'_alt" type="text" placeholder="'.$placeholder.' alt" ng-model="main.datas.'.$meta.'_alt" ng-value="main.datas.'.$meta.'_alt"/>';


   		//provide a button from which to change the media
   		echo '<p><a href="#" ng-click="main.addMedia(\''.$meta.'\')" class="button insert-media add_media" data editor="content" title="Add Media"><span class="wp-media-buttons-icon"></span>Update Media</a></p>';
   		echo '</div>';
   	}


   	public static function print_gallery_field($meta, $label, $placeholder, $post, $help_text){
   		//initialize this particular value

   		echo "<div class='media-field cf'>";

   		$meta_alt = $meta.'_alt';
   		echo '<div ng-init=\'
   		    main.datas.' . $meta . '='. $post->$meta . ';
   		\'></div>';

   		//set the actual input field
   		echo '<label for="'.$meta.'">'.$label.'</label>';

   		//display the chosen image, if it's set
   		echo "<div class='gallery-images row'>";
   			echo '<div class="gallery-image col-md-3" ng-repeat="img in main.datas.' . $meta . ' track by $index">';
   				echo '<p>';
   					echo '<button type="button" ng-click="main.moveItemUp(main.datas.' . $meta . ', $index)" class="button">Left</button> ';
   					echo '<button type="button" ng-click="main.moveItemDown(main.datas.' . $meta . ', $index)" class="button">Right</button> ';
   					echo '<button type="button" ng-click="main.removeItem(main.datas.' . $meta . ', $index)" class="button">Remove</button>';
   				echo '</p>';
   				echo '<img style="max-width:100%;" ng-src="{{img}}"/>';
   			echo '</div>';
   		echo "</div>";

   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}

   		//Hidden field to store the gallery array
   		echo '<input name="'.$meta.'" id="'.$meta.'" type="hidden" ng-value="main.datas.'.$meta.' | json"/>';

   		//provide a button from which to change the media
   		echo '<p><a href="#" ng-click="main.pushMedia(main.datas, \''.$meta.'\')" class="button insert-media add_media" data editor="content" title="Add Media"><span class="wp-media-buttons-icon"></span>Add Image to Gallery</a></p>';
   		echo '</div>';
   	}

   	public static function print_related_cpt_field($meta, $label, $placeholder, $post, $help_text) {
   		//Related posts are defined as any post in the same post type as the current post
   		$args = array(
   			'post_type' => $post->post_type,
   			'posts_per_page' => -1,
   		);
   		$related_posts = new WP_Query($args);

   		echo "<div class='media-field cf'>";

   		$meta_alt = $meta.'_alt';
   		echo '<div ng-init=\'
   		    main.datas.' . $meta . '='. $post->$meta . ';
   		\'></div>';

   		//set the actual input field
   		echo '<label for="'.$meta.'">'.$label.'</label>';

			echo '<p ng-repeat="post in main.datas.' . $meta . ' track by $index">';
				echo '<select ng-model="post.id">';
					echo '<option value="">Select post...</option>';
					//Loop through related posts and display
					if ($related_posts->have_posts()) : while ($related_posts->have_posts()) : $related_posts->the_post();
						echo '<option value=' . get_the_ID() . '>' . get_the_title() . '</option>';
					endwhile; endif;
					wp_reset_query();
				echo '</select> ';
				echo '<button type="button" ng-click="main.moveItemUp(main.datas.' . $meta . ', $index)" class="button">Up</button> ';
				echo '<button type="button" ng-click="main.moveItemDown(main.datas.' . $meta . ', $index)" class="button">Down</button> ';
				echo '<button type="button" ng-click="main.removeItem(main.datas.' . $meta . ', $index)" class="button">Remove</button>';
			echo '</p>';

   		if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}

   		//Hidden field to store the gallery array
   		echo '<input name="'.$meta.'" id="'.$meta.'" type="hidden" ng-value="main.datas.'.$meta.' | json"/>';

   		//provide a button from which to change the media
   		echo '<p><button type="button" ng-click="main.addItem(main.datas, \''.$meta.'\')" class="button" title="Add Related">Add Related</button></p>';
   		echo '</div>';
   	}



   	public static function print_json_field($meta, $label, $post, $help_text, $template, $controller){
		$to_print = $post->$meta;
		error_log(serialize($to_print));
		if($to_print){
			echo "<script> var ".$meta."Value = " . json_encode($to_print) . " </script>";
		}
		else{
			echo "<script> var ".$meta."Value = '' </script>";
		}

   		echo "<div class='json-field cf' ng-controller='".$controller."'>";

   		//set the actual input field
   		echo '<label for="'.$meta.'">'.$label.'</label>';

        if($help_text){
   			echo '<p class="sg-help-text">' . $help_text . '</p>';
   		}
                
   		echo $template;

   		echo '<input type="hidden" ng-model="json_to_save" ng-value="json_to_save" name="'.$meta.'"/>';

   		echo "</div>";
   	}

	//given a user ID and a meta key to check for, fetches all invoices for that individual
	//iif no meta_key is passed, auto-search user
	//exempt will allow the user to skip authentication
	public static function get_posts_for_user($uid, $meta_key=false, $exempt=false){
		//make sure that this is the user that we're checking or that they're an admin
		//if exempt is passed to this as true, then the user doesn't have to be authenticated or an admin
		if( ! $exempt ){
			
			static::is_user_or_admin($uid);
		}

		if( ! $meta_key ){
			$meta_key = static::$post_type_name . '_owner';
		}

  		//get invoices
		$args = array(
			'post_type'  => static::$post_type_name,
			'meta_key'   => $meta_key,
			'meta_value' => $uid,
		);
		$posts = new WP_Query( $args );

		$posts = $posts->posts;
		$to_return = array();

		//get meta for each
		foreach ($posts as $post) {
			//if the user is the owner, and the current is not exempt, then return

			if( $exempt ){
				array_push($to_return, static::post_get_full($post, static::$all_fields));
			}
			else if(self::user_is_owner($post->ID, $uid)){
				array_push($to_return, static::post_get_full($post, static::$all_fields));
			}
			else{
				error_log('failed inside');
				APIResponse::init(FALSE, "You don't have permission to add that!", array());
			}
		}
		return $to_return;
	}

	/*
		author: @paulnurkkala
		description: Given a meta key and a meta value, get full posts for each
	*/
	public static function get_posts_by_key($meta_key, $meta_value){

		$args = array(
			'nopaging'    => TRUE,
            'post_status' => 'publish',
            'post_type'   => static::$post_type_name,
            'meta_key'    => $meta_key,
            'meta_value'  => $meta_value
        );

        $query = new WP_Query($args);
        $posts = $query->get_posts();

        $return_posts = array();

        foreach ($posts as $post) {
        	array_push($return_posts, static::post_get_full($post, static::$all_fields));
        }

        return $return_posts;
	}

	public static function is_user_or_admin($uid){
		$current_user_id = wp_get_current_user()->ID;
		$user_id = $uid;

		if( $current_user_id != $user_id){
			if( ! static::user_is_administrator($current_user_id)){
				APIResponse::init(FALSE, 'You do not have permission to do that.', array());
			}
		}

	}

	/*
	    author: @paulnurkkala
	    description:
    	   given an associative array of data, checks to make sure that all required fields are filled out
   	       returns an associative array containing:
   	            success: whether or not this successfully validated
   	            message: why it failed, if it failed
   	*/
	public static function check_required($data){
		$required_fields = static::get_required_fields();

		foreach ($required_fields as $field) {
			if ( empty($data[$field]) )
			{
				return array('success'=> FALSE, 'message'=>'Missing ' . $field);
			}
		}

		return array('success'=>True, 'message'=>'');
	}

	/*
		author: @paulnurkkala
		description: just runs "check required" but it will fail with an APIResponse if it fails, rather than passing control back to the caller
	*/
	public static function api_check_required($data){
		$passed_required = static::check_required($data);

		if ( ! $passed_required['success'] ){
			APIResponse::init(FALSE, $passed_required['message'], array());
		}

	}

	public static function get_required_fields(){
		$all_fields = static::$all_fields;

		$required_fields = array();
		foreach ($all_fields as $field) {
 			if($field['required']){
 				array_push($required_fields, $field['meta']);
 			}
		}

		return $required_fields;
	}

	public static function get_all_fields(){
		$all_fields = static::$all_fields;

		$flat_fields = array();
		foreach ($all_fields as $field) {
			array_push($flat_fields, $field['meta']);
		}

		return $flat_fields;
	}

	//loops through $api_actions and creates listeners for the API calls
	public static function init_api_actions(){
		foreach (static::$api_actions as $call) {
			add_action("wp_ajax_nopriv_".$call['api'], array( get_called_class(), $call['func'] ));
			add_action("wp_ajax_".$call['api'],        array( get_called_class(), $call['func'] ));
		}
	}
}

// Local Variables:
// mode: php
// End: