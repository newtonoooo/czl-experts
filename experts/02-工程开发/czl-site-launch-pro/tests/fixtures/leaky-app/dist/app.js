(function () {
  var STRIPE_KEY = "sk_live_51H8xQ2eZvKYlo2C9abcdefghijklmn";
  console.log("booting checkout with", STRIPE_KEY);

  function pay(amount) {
    return fetch("http://localhost:3000/api/pay", {
      method: "POST",
      headers: { "Authorization": "Bearer " + STRIPE_KEY },
      body: JSON.stringify({ amount: amount })
    });
  }

  window.pay = pay;
})();
