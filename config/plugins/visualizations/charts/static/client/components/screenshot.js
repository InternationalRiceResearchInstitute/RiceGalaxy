/** This class enables users to export/download a chart as PNG, SVG or PDF. */
define( [ 'libs/underscore' ], function( _ ) {
    /** PNG export */
    function createPNG (options) {
        if ( options.$el.find( 'svg' ).length > 0 ) {
            _svg2png( options );
        } else {
            _canvas2png( options.$el.find( '.charts-viewport-canvas' ) );
        }
    };

    /** Convert canvas to png */
    function _canvas2png( $canvas ) {
        try {
            if ( $canvas.width() !== 0 && $canvas.height() !== 0) {
                var newCanvas = document.createElement( 'canvas' );
                newCanvas.width = $canvas.outerWidth( true );
                newCanvas.height = $canvas.outerHeight( true );
                var newContext = newCanvas.getContext( '2d' );
                newContext.save();
                newContext.fillStyle = 'rgb(255,255,255)';
                newContext.fillRect( 0,0, newCanvas.width, newCanvas.height );
                newContext.restore();
                newContext.translate( 0, 0 );
                newContext.textAlign = 'left';
                newContext.textBaseline = 'top';
                function _toImage( $el, x_offset, y_offset ) {
                    var tagname = $el.prop( 'tagName' ).toLowerCase();
                    var p = $el.position();
                    var left = x_offset + p.left + parseInt( $el.css( 'marginLeft' ), 10 ) + parseInt( $el.css( 'borderLeftWidth' ), 10 ) + parseInt( $el.css( 'paddingLeft' ), 10 );
                    var top = y_offset + p.top + parseInt( $el.css( 'marginTop' ), 10 ) + parseInt( $el.css( 'borderTopWidth' ), 10 ) + parseInt( $el.css( 'paddingTop' ), 10 );
                    var w = newCanvas.width;
                    if ( tagname == 'div' || tagname == 'span' ) {
                        $el.children().each( function() { _toImage( $( this ), left, top ) } );
                    } else if ( tagname == 'canvas' ) {
                        newContext.drawImage( $el[ 0 ], left, top );
                    }
                }
                $canvas.children().each( function() { _toImage( $( this ), 0, 0 ) } );
                var imgData = newCanvas.toDataURL( 'image/png' );
                if ( imgData ) {
                    window.location.href = imgData.replace( 'image/png', 'image/octet-stream' );
                }
            }
        } catch ( err ) {
            console.debug( 'FAILED - screenshot::_canvas2png() - ' + err );
            if (options.error) {
                options.error( 'Please reduce your visualization to a single panel and try again.' );
            }
        }
    };

    /** Convert svg to png */
    function _svg2png ( options ) {
        var scale = 5;
        var xml = toXML( options );
        var canvas = document.createElement( 'canvas' );
        var context = canvas.getContext( '2d' );
        var source = new Image();
        var $container = $( '<div style="display:none;"/>' ).append( $ ( canvas ) );
        $( 'body' ).append( $container );
        canvas.width = xml.width * scale;
        canvas.height = xml.height * scale;
        source.src = 'data:image/svg+xml;base64,' + btoa( xml.string );
        source.onload = function() {
            context.drawImage( source, 0, 0, canvas.width, canvas.height );
            window.location.href = canvas.toDataURL( 'image/png' ).replace( 'image/png', 'image/octet-stream' );
            $container.remove();
        }
    };

    /** SVG export */
    function createSVG (options) {
        window.location.href = 'data:none/none;base64,' + btoa(toXML(options).string);
    };

    /** PDF export */
    function createPDF( options ) {
        var xml = toXML( options );
        var data = {
            filename    : 'visualization',
            type        : 'application/pdf',
            height      : xml.height,
            width       : xml.width,
            scale       : 2,
            svg         : xml.string
        };
        var $el = $( 'body' );
        var form = $el.find( '#viewport-form' );
        if ( form.length === 0 ) {
            form = $( '<form>', {
                id      : 'viewport-form',
                method  : 'post',
                action  : 'http://export.highcharts.com/',
                display : 'none'
            });
            $el.append( form );
        }
        form.empty();
        for (var name in data ) {
            var input = $( '<input/>', {
                type    : 'hidden',
                name    : name,
                value   : data[ name ]
            });
            form.append( input );
        }
        try {
            form.submit();
        } catch( err ) {
            console.log( err );
        }
    };

    /** XML export */
    function toXML( options ) {
        var $svg = options.$el.find( 'svg' );
        if ( $svg.length == 0 ) {
            if ( options.error ) {
                options.error( 'No SVG found. This visualization type does not support SVG/PDF export.' );
                return;
            }
        }
        var $el = options.$el;
        var nsvgs  = $svg.length;
        var height = parseInt( $svg.first().css( 'height' ) );
        var width  = parseInt( $svg.first().css( 'width' ) );
        var serializer = new XMLSerializer();
        var $composite = $( '<svg/>' ).attr( { version: '1.1', xmlns: 'http://www.w3.org/2000/svg', width: width * nsvgs, height: height } );
        var xmlString = '';
        var offsetX = 0;
        $svg.each(function() {
            var $svg = $( this ).clone();
            _inline( $svg );
            var $g = $( '<g transform="translate(' + offsetX + ', 0)">' ).attr( 'xmlns', 'http://www.w3.org/2000/svg' );
            $g.append( $svg.find( 'g' ).first() );
            $composite.append( $g );
            offsetX += width;
        });
        return {
            string  : serializer.serializeToString( $composite[ 0 ] ),
            height  : height,
            width   : width
        }
    };

    /** inlines CSS code */
    function _inline( $target ) {
        for ( var sheet_id in document.styleSheets ) {
            var sheet = document.styleSheets[ sheet_id ];
            var rules = sheet.cssRules;
            if ( rules ) {
                for ( var idx = 0, len = rules.length; idx < len; idx++ ) {
                    try {
                        $target.find( rules[ idx ].selectorText ).each( function ( i, elem ) {
                            elem.style.cssText += rules[idx].style.cssText;
                        });
                    } catch( err ) {}
                }
            }
        }
    };

    return {
        createPNG: createPNG,
        createSVG: createSVG,
        createPDF: createPDF
    };
});