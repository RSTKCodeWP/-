# WP CustPostType
## @paulnurkkala 

To add to your projcet: 

Include in your project, add the CustPostType.php file to your project directory, and then include with: 

```
	require('/path/to/CustPostType.php')
```
Then, when you want to start building your own custom post types, simply create a new folder called "PostType.php" and copy the "ExampleExtension.php" file in and start changing variables. The example given is for creating a "GlobalOptions" custom post type for your project so that you can have global options that are modifiable by the end user. 

How I set up Global Options: 
* Include CustPostType.php
* Create and include GlobalOptions.php with the ExampleExtension.php code 
* Download and install the plugin "Advanced Custom Fields" (ACF)
* Within ACF plugin, create a fieldset that has set: "Show this field group if "Post" is equal to "All Global Options" where "All Global Options is the name of the fieldset that you created. 
* Use ACF to create all the fields that you will need your users to have access to. 
* In the URL of the Global options, notice the ID of the post type, you will need this for accessing the global options that you are creating here. 
* When you are ready to use your global options in the theme of your website, simply access like this:

```
<?php get_field('field_name_from_acf', GlobalOptionsID); ?>
```

Where 
* field_name_from_acf is the underscore_based fieldname that is created by ACF and
* GlobalOptionsID is the ID from the URL that I told you to note


So, an option called "make_header_blue" with global options ID 23 would be: 
```
<?php 
	if(get_field('make_header_blue', 23)){
    	//code to make the header blue
    }
?>
```

Once setup, this method is very fast and very powerful for fully customizing the global options of a wordpress site.

Further inspection of the CustPostType class will reveal that there's a lot more power than is simply described above, but I will have to wait for a later date to be able to show all of what it can do. I spent about 4-5 months contiuning to add to this class to make it better and better.