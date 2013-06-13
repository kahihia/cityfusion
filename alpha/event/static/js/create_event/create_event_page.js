;(function($, window, document, undefined) {
    'use strict';

    function CreateEventPage(){
        this.doNotSubmitOnEnter();
        this.initBalloons();
        this.initVenueAutocomplete();
        this.initDescriptionField();
    }

    CreateEventPage.prototype = {
        doNotSubmitOnEnter: function(){
            var keyStop = {
                13: "input, textarea", // stop enter = submit
                end: null
            };

            $(document).bind("keydown", function(event){
                var selector = keyStop[event.which];

                if(selector !== undefined && $(event.target).is(selector)) {
                    event.preventDefault(); //stop event
                }
                return true;
            });
        },
        initBalloons: function(){
            $.balloon.defaults.classname = "hintbox";
            $.balloon.defaults.css = {};
            var ballons = $(".balloon");
            $(ballons).each(function(){
                var content = $(this).siblings(".balloon-content");
                $(this).balloon({
                    contents:content,
                    position:"left bottom",
                    tipSize: 0,
                    offsetX:0,//$.browser.msie?0:25,
                    offsetY:25,//$.browser.msie?25:0,
                    showDuration: 500, hideDuration: 0,
                    showAnimation: function(d) { this.fadeIn(d); }
                });
            });
        },
        initVenueAutocomplete: function(){
            this.venueAutocomplete = new window.VenueAutocomplete(
                $('#id_city_0'),
                $('#id_city_1'),
                $('.location_map')
            );

        },
        initDescriptionField: function(){
            var value = $("#id_description_json").val();
            $("#id_description").description();
            
            if(value){
                var json = JSON.parse(value);
                $("#id_description").html(json["default"]);
                $("#id_description").data("description").setValue(json);
                $("#id_description").data("description").saveCurrentDay();
            }
        }
    };

    $(document).on("ready page:load", function(){
        window.createEventPage = new CreateEventPage();
    });

})(jQuery, window, document);
