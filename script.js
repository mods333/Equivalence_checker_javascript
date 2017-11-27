var x;
var y;
var text;
var otherText;

(function() {
    function fibonacci(x) {
        return x <= 1 ? x : fibonacci(x - 1) + fibonacci(x - 2);
    }
    
    function add2(x) {
        return x + 2;
    }

    function setHelloWorld() {
        return 'Hello world!';
    }

    function setFooBar() {
        return 'Foo Bar';
    }
    
    x = fibonacci(10);
    y = add2(x);
    if (y < 50) {
        text = setHelloWorld();
        otherText = setFooBar();
    } else {
        text = setFooBar();
        otherText = setHelloWorld();
    }
    
})();
