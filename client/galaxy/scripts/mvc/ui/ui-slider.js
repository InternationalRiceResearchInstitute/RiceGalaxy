define([ 'utils/utils' ], function( Utils ) {
    var View = Backbone.View.extend({
        initialize : function( options ) {
            var self = this;
            this.model = options && options.model || new Backbone.Model({
                id       : Utils.uid(),
                min      : null,
                max      : null,
                step     : null,
                precise  : false,
                split    : 10000,
                value    : null,
                onchange : function(){}
            }).set( options );

            // create new element
            this.setElement( this._template() );
            this.$el.attr( 'id', this.model.id );
            this.$text   = this.$( '.ui-form-slider-text' );
            this.$slider = this.$( '.ui-form-slider-element' );

            // add text field event
            var pressed = [];
            this.$text.on( 'change', function () {
                self.value( $( this ).val() );
            }).on( 'keyup', function( e ) {
                pressed[e.which] = false;
            }).on( 'keydown', function ( e ) {
                var v = e.which;
                pressed[ v ] = true;
                if ( self.model.get( 'is_workflow' ) && pressed[ 16 ] && v == 52 ) {
                    self.value( '$' );
                    event.preventDefault();
                } else if (!( v == 8 || v == 9 || v == 13 || v == 37 || v == 39 || ( v >= 48 && v <= 57 && !pressed[ 16 ] ) || ( v >= 96 && v <= 105 )
                    || ( ( v == 190 || v == 110 ) && $( this ).val().indexOf( '.' ) == -1 && self.model.get( 'precise' ) )
                    || ( ( v == 189 || v == 109 ) && $( this ).val().indexOf( '-' ) == -1 )
                    || self._isParameter( $( this ).val() )
                    || pressed[ 91 ] || pressed[ 17 ] ) ) {
                    event.preventDefault();
                }
            });

            // build slider, cannot be rebuild in render
            var opts = this.model.attributes;
            this.has_slider = opts.max !== null && opts.min !== null && opts.max > opts.min;
            var step = opts.step;
            if ( !step ) {
                if ( opts.precise && this.has_slider ) {
                    step = ( opts.max - opts.min ) / opts.split;
                } else {
                    step = 1.0;
                }
            }
            if ( this.has_slider ) {
                this.$text.addClass( 'ui-form-slider-left' );
                this.$slider.slider( { min: opts.min, max: opts.max, step: step } )
                            .on( 'slide', function ( event, ui ) { self.value( ui.value ) } );
            } else {
                this.$slider.hide();
            }

            // add listeners
            this.listenTo( this.model, 'change', this.render, this );
            this.render();
        },

        render: function() {
            var value = this.model.get( 'value' );
            this.has_slider && this.$slider.slider( 'value', value );
            value !== this.$text.val() && this.$text.val( value );
        },

        /** Set and return the current value */
        value : function ( new_val ) {
            var options = this.model.attributes;
            if ( new_val !== undefined ) {
                if ( new_val !== null && new_val !== '' && !this._isParameter( new_val ) ) {
                    isNaN( new_val ) && ( new_val = 0 );
                    !options.precise && ( new_val = Math.round( new_val ) );
                    options.max !== null && ( new_val = Math.min( new_val, options.max ) );
                    options.min !== null && ( new_val = Math.max( new_val, options.min ) );
                }
                this.model.set( 'value', new_val );
                this.model.trigger( 'change' );
                options.onchange( new_val );
            }
            return this.model.get( 'value' );
        },

        /** Return true if the field contains a workflow parameter i.e. $('name') */
        _isParameter: function( value ) {
            return this.model.get( 'is_workflow' ) && String( value ).substring( 0, 1 ) === '$';
        },

        /** Slider template */
        _template: function() {
            return  '<div class="ui-form-slider">' +
                        '<input class="ui-form-slider-text" type="text"/>' +
                        '<div class="ui-form-slider-element"/>' +
                    '</div>';
        }
    });

    return {
        View : View
    };
});