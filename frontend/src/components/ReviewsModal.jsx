import { Check, Star, X } from "lucide-react";
import { useEffect, useState } from "react";

import { getProductReviews, moderateReview } from "../services/reviewService";
import ModalShell from "./ModalShell";
import "./ReviewsModal.css";


function ReviewsModal({ businessId, product, onClose, onApproved }) {
  const [reviews, setReviews] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [workingReviewId, setWorkingReviewId] = useState("");

  useEffect(() => {
    let requestIsCurrent = true;

    if (!businessId || !product?.id) return undefined;
    setIsLoading(true);
    setErrorMessage("");

    getProductReviews(businessId, product.id)
      .then((records) => {
        if (requestIsCurrent) setReviews(records);
      })
      .catch((error) => {
        if (requestIsCurrent) setErrorMessage(error.message);
      })
      .finally(() => {
        if (requestIsCurrent) setIsLoading(false);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [businessId, product?.id]);

  async function changeStatus(review, status) {
    setWorkingReviewId(review.id);
    setErrorMessage("");

    try {
      const updatedReview = await moderateReview(businessId, review.id, status);
      setReviews((current) =>
        current.map((item) => (item.id === review.id ? updatedReview : item)),
      );
      if (status === "approved") onApproved?.(product.id);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setWorkingReviewId("");
    }
  }

  return (
    <ModalShell
      isOpen={Boolean(product)}
      title={`${product?.name ?? "Product"} reviews`}
      description="Approve verified reviews before they appear in the public catalogue and chatbot."
      onClose={onClose}
      size="large"
    >
      {isLoading && <p className="reviews-modal__notice">Loading reviews...</p>}
      {errorMessage && <p className="reviews-modal__notice reviews-modal__notice--error" role="alert">{errorMessage}</p>}

      <div className="reviews-modal__list">
        {reviews.map((review) => (
          <article className="reviews-modal__review" key={review.id}>
            <header>
              <div>
                <strong>{review.customerName}</strong>
                <span>{review.verifiedPurchase ? "Verified purchase" : "Customer review"}</span>
              </div>
              <span className={`reviews-modal__status reviews-modal__status--${review.status}`}>
                {review.status}
              </span>
            </header>

            <div className="reviews-modal__stars" aria-label={`${review.rating} out of 5 stars`}>
              {Array.from({ length: 5 }, (_, index) => (
                <Star
                  key={index}
                  size={16}
                  fill={index < review.rating ? "currentColor" : "none"}
                />
              ))}
            </div>
            <p>{review.reviewText}</p>
            <small>Order {review.orderNumber}</small>

            {review.status === "pending" && (
              <footer>
                <button
                  type="button"
                  onClick={() => changeStatus(review, "rejected")}
                  disabled={workingReviewId === review.id}
                >
                  <X size={16} /> Reject
                </button>
                <button
                  className="reviews-modal__approve"
                  type="button"
                  onClick={() => changeStatus(review, "approved")}
                  disabled={workingReviewId === review.id}
                >
                  <Check size={16} /> Approve
                </button>
              </footer>
            )}
          </article>
        ))}

        {!isLoading && reviews.length === 0 && (
          <p className="reviews-modal__empty">No reviews have been submitted for this product yet.</p>
        )}
      </div>
    </ModalShell>
  );
}

export default ReviewsModal;
