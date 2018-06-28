define([ 'jquery' ], function( jQuery ){
'use_strict';

var $ = jQuery;

// ============================================================================
// TODO: unify popup menus and/or eliminate this
/**
 * Sets up popupmenu rendering and binds options functions to the appropriate links.
 * initial_options is a dict with text describing the option pointing to either (a) a
 * function to perform; or (b) another dict with two required keys, 'url' and 'action' (the
 * function to perform. (b) is useful for exposing the underlying URL of the option.
 */
function make_popupmenu(button_element, initial_options) {
    /*  Use the $.data feature to store options with the link element.
        This allows options to be changed at a later time
    */
    var element_menu_exists = (button_element.data("menu_options"));
    button_element.data("menu_options", initial_options);

    // If element already has menu, nothing else to do since HTML and actions are already set.
    if (element_menu_exists) { return; }

    button_element.bind("click.show_popup", function(e) {
        // Close existing visible menus
        $(".popmenu-wrapper").remove();

        // Need setTimeouts so clicks don't interfere with each other
        setTimeout( function() {
            // Dynamically generate the wrapper holding all the selectable options of the menu.
            var menu_element = $( "<ul class='dropdown-menu' id='" + button_element.attr('id') + "-menu'></ul>" );
            var options = button_element.data("menu_options");
            if (_.size(options) <= 0) {
                $("<li>No Options.</li>").appendTo(menu_element);
            }
            $.each( options, function( k, v ) {
                if (v) {
                    // Action can be either an anonymous function and a mapped dict.
                    var action = v.action || v;
                    menu_element.append( $("<li></li>").append( $("<a>").attr("href", v.url).html(k).click(action) ) );
                } else {
                    menu_element.append( $("<li></li>").addClass( "head" ).append( $("<a href='#'></a>").html(k) ) );
                }
            });
            var wrapper = $( "<div class='popmenu-wrapper' style='position: absolute;left: 0; top: -1000;'></div>" )
                .append( menu_element ).appendTo( "body" );

            var x = e.pageX - wrapper.width() / 2 ;
            x = Math.min( x, $(document).scrollLeft() + $(window).width() - $(wrapper).width() - 5 );
            x = Math.max( x, $(document).scrollLeft() + 5 );

            wrapper.css({
               top: e.pageY,
               left: x
            });
        }, 10);

        setTimeout( function() {
            // Bind click event to current window and all frames to remove any visible menus
            // Bind to document object instead of window object for IE compat
            var close_popup = function(el) {
                $(el).bind("click.close_popup", function() {
                    $(".popmenu-wrapper").remove();
                    el.unbind("click.close_popup");
                });
            };
            close_popup( $(window.document) ); // Current frame
            close_popup( $(window.top.document) ); // Parent frame
            for (var frame_id = window.top.frames.length; frame_id--;) { // Sibling frames
                var frame = $(window.top.frames[frame_id].document);
                close_popup(frame);
            }
        }, 50);

        return false;
    });

}

/**
 *  Convert two seperate (often adjacent) divs into galaxy popupmenu
 *  - div 1 contains a number of anchors which become the menu options
 *  - div 1 should have a 'popupmenu' attribute
 *  - this popupmenu attribute contains the id of div 2
 *  - div 2 becomes the 'face' of the popupmenu
 *
 *  NOTE: make_popup_menus finds and operates on all divs with a popupmenu attr (no need to point it at something)
 *          but (since that selector searches the dom on the page), you can send a parent in
 *  NOTE: make_popup_menus, and make_popupmenu are horrible names
 */
function make_popup_menus( parent ) {
    // find all popupmenu menu divs (divs that contains anchors to be converted to menu options)
    //  either in the parent or the document if no parent passed
    parent = parent || document;
    $( parent ).find( "div[popupmenu]" ).each( function() {
        var options = {};
        var menu = $(this);

        // find each anchor in the menu, convert them into an options map: { a.text : click_function }
        menu.find( "a" ).each( function() {
            var link = $(this),
                link_dom = link.get(0),
                confirmtext = link_dom.getAttribute( "confirm" ),
                href = link_dom.getAttribute( "href" ),
                target = link_dom.getAttribute( "target" );

            // no href - no function (gen. a label)
            if (!href) {
                options[ link.text() ] = null;

            } else {
                options[ link.text() ] = {
                    url: href,
                    action: function( event ) {

                        // if theres confirm text, send the dialog
                        if ( !confirmtext || confirm( confirmtext ) ) {
                            // link.click() doesn't use target for some reason,
                            // so manually do it here.
                            if (target) {
                                window.open(href, target);
                                return false;
                            }
                            // For all other links, do the default action.
                            else {
                                link.click();
                            }
                        } else {
                                event.preventDefault();
                        }

                    }
                };
            }
        });
        // locate the element with the id corresponding to the menu's popupmenu attr
        var box = $( parent ).find( "#" + menu.attr( 'popupmenu' ) );

        // For menus with clickable link text, make clicking on the link go through instead
        // of activating the popup menu
        box.find("a").bind("click", function(e) {
            e.stopPropagation(); // Stop bubbling so clicking on the link goes through
            return true;
        });

        // attach the click events and menu box building to the box element
        make_popupmenu(box, options);
        box.addClass("popup");
        menu.remove();
    });
}

// ============================================================================
    return {
        make_popupmenu : make_popupmenu,
        make_popup_menus : make_popup_menus
    };
});
